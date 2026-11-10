"""Strict verification of Keycloak access tokens for protected API routes."""

from functools import lru_cache
from typing import Any
from urllib.parse import quote

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    issuer: str = Field(
        default="http://localhost:8080/realms/local-ai",
        validation_alias="KEYCLOAK_ISSUER",
    )
    internal_url: str = Field(
        default="http://keycloak:8080",
        validation_alias="KEYCLOAK_INTERNAL_URL",
    )
    realm: str = Field(default="local-ai", validation_alias="KEYCLOAK_REALM")
    client_id: str = Field(
        default="local-ai-frontend",
        validation_alias="KEYCLOAK_CLIENT_ID",
    )
    expected_audience: str | None = Field(
        default=None,
        validation_alias="KEYCLOAK_EXPECTED_AUDIENCE",
    )

    @field_validator("expected_audience", mode="before")
    @classmethod
    def empty_audience_is_unset(cls, value: Any) -> Any:
        return None if value == "" else value


@lru_cache(maxsize=1)
def get_keycloak_settings() -> KeycloakSettings:
    return KeycloakSettings()


def jwks_url(settings: KeycloakSettings) -> str:
    realm = quote(settings.realm, safe="")
    return (
        f"{settings.internal_url.rstrip('/')}/realms/{realm}"
        "/protocol/openid-connect/certs"
    )


@lru_cache(maxsize=8)
def get_jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, timeout=5)


class KeycloakTokenVerifier:
    """Verify RS256 tokens and bind them to the configured OIDC client."""

    def __init__(self, settings: KeycloakSettings | None = None) -> None:
        self.settings = settings or get_keycloak_settings()

    def _signing_key(self, token: str) -> Any:
        client = get_jwks_client(jwks_url(self.settings))
        return client.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> dict[str, Any]:
        try:
            signing_key = self._signing_key(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                options={
                    "verify_aud": False,
                    "require": ["exp", "iss", "sub", "azp"],
                },
            )
        except PyJWKClientConnectionError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Identity verification service is unavailable.",
            ) from error
        except (PyJWKClientError, jwt.InvalidTokenError, ValueError) as error:
            raise unauthorized() from error

        if claims.get("azp") != self.settings.client_id:
            raise unauthorized()

        if self.settings.expected_audience:
            audience = claims.get("aud", [])
            audiences = [audience] if isinstance(audience, str) else audience
            if not isinstance(audiences, list) or self.settings.expected_audience not in audiences:
                raise unauthorized()

        return claims


@lru_cache(maxsize=1)
def get_token_verifier() -> KeycloakTokenVerifier:
    return KeycloakTokenVerifier()


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: KeycloakTokenVerifier = Depends(get_token_verifier),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    return verifier.verify(credentials.credentials)\n