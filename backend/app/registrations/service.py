"""Orchestrates rate-limited OTP registration, delivery, and activation."""

import secrets
from functools import lru_cache
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.registrations.keycloak_admin import (
    DuplicateKeycloakAccount,
    KeycloakAdminUnavailable,
    KeycloakRegistrationAdmin,
)
from app.registrations.mailer import EmailDeliveryError, RegistrationMailer
from app.registrations.security import RegistrationCrypto
from app.registrations.settings import RegistrationSettings, get_registration_settings
from app.registrations.store import RateLimitExceeded, RegistrationStore
from app.schemas.registration import RegistrationRequest


class RegistrationService:
    def __init__(
        self,
        store: RegistrationStore,
        crypto: RegistrationCrypto,
        mailer: RegistrationMailer,
        keycloak: KeycloakRegistrationAdmin,
    ) -> None:
        self.store = store
        self.crypto = crypto
        self.mailer = mailer
        self.keycloak = keycloak

    async def _rate_limit(self, ip: str, endpoint: str, *, limit: int, window: int) -> None:
        try:
            await self.store.enforce_rate_limit(
                self.crypto.rate_limit_key(ip, endpoint), limit=limit, window_seconds=window
            )
        except RateLimitExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait before trying again.",
                headers={"Retry-After": str(error.retry_after)},
            ) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registration is temporarily unavailable.",
            ) from error

    async def register(self, data: RegistrationRequest, ip: str) -> dict[str, object]:
        await self._rate_limit(ip, "register", limit=5, window=3600)
        email = str(data.email)
        username = data.username
        try:
            if await self.keycloak.account_exists(username, email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That username or email address is already registered.",
                )
        except KeycloakAdminUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
            ) from error

        registration_id = uuid4()
        otp = f"{secrets.randbelow(10_000):04d}"
        salt = self.crypto.otp_salt()
        digest = self.crypto.otp_digest(registration_id, salt, otp)
        password_nonce, password_ciphertext = self.crypto.encrypt_password(
            data.password, registration_id
        )
        try:
            await self.store.create_pending(
                registration_id=registration_id,
                username=username,
                email=email,
                first_name=data.first_name,
                last_name=data.last_name,
                password_nonce=password_nonce,
                password_ciphertext=password_ciphertext,
                otp_salt=salt,
                otp_hash=digest,
                otp_code=otp,
                send_email=self.mailer.send_otp,
            )
        except IntegrityError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username or email address is already awaiting verification.",
            ) from error
        except EmailDeliveryError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The verification email could not be sent. Please try again.",
            ) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registration is temporarily unavailable.",
            ) from error
        return {
            "registration_id": registration_id,
            "email": email,
            "expires_in_seconds": 300,
            "resend_in_seconds": 60,
        }

    async def verify(self, registration_id: UUID, otp: str, ip: str) -> dict[str, str]:
        await self._rate_limit(ip, "verify", limit=30, window=900)

        async def provision(account: dict[str, str], password: str) -> None:
            await self.keycloak.provision_verified_user(account, password)

        try:
            result = await self.store.verify(
                registration_id,
                otp=otp,
                crypto=self.crypto,
                provision_user=provision,
            )
        except DuplicateKeycloakAccount as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username or email address is already registered.",
            ) from error
        except KeycloakAdminUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Account activation could not be completed. Retry with the same code.",
            ) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Account activation could not be completed. Retry with the same code.",
            ) from error

        match result["status"]:
            case "verified":
                return {"status": "verified", "email": str(result["email"])}
            case "incorrect":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="That code is incorrect. Check the email and try again.",
                )
            case "locked":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many incorrect codes. Start registration again later.",
                )
            case "expired":
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="That code expired. Start registration again to get a new one.",
                )
            case _:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="This registration is no longer available.",
                )

    async def resend(self, registration_id: UUID, ip: str) -> dict[str, int | str]:
        await self._rate_limit(ip, "resend", limit=10, window=3600)
        otp = f"{secrets.randbelow(10_000):04d}"
        salt = self.crypto.otp_salt()
        digest = self.crypto.otp_digest(registration_id, salt, otp)
        try:
            result = await self.store.resend(
                registration_id,
                otp_salt=salt,
                otp_hash=digest,
                otp_code=otp,
                send_email=self.mailer.send_otp,
            )
        except EmailDeliveryError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The new verification email could not be sent. The current code remains valid.",
            ) from error
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Registration is temporarily unavailable.",
            ) from error

        match result["status"]:
            case "sent":
                return {"resend_in_seconds": 60, "expires_in_seconds": 300}
            case "cooldown":
                retry_after = int(result["retry_after"])
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {retry_after} seconds before requesting another code.",
                    headers={"Retry-After": str(retry_after)},
                )
            case "limit":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="The resend limit has been reached. Start registration again later.",
                )
            case "expired":
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="This registration expired. Start again to request a new code.",
                )
            case "locked":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="This registration is locked. Start again to request a new code.",
                )
            case _:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="This registration is no longer available.",
                )


@lru_cache(maxsize=1)
def get_registration_service() -> RegistrationService:
    settings: RegistrationSettings = get_registration_settings()
    return RegistrationService(
        store=RegistrationStore(settings.database_url),
        crypto=RegistrationCrypto(settings.key_dir),
        mailer=RegistrationMailer(settings),
        keycloak=KeycloakRegistrationAdmin(settings),
    )
