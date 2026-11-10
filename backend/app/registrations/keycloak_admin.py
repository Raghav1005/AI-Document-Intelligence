"""Minimal Keycloak service-account operations for pending registrations."""

from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.registrations.settings import RegistrationSettings


class DuplicateKeycloakAccount(Exception):
    pass


class KeycloakAdminUnavailable(Exception):
    pass


class KeycloakRegistrationAdmin:
    def __init__(self, settings: RegistrationSettings) -> None:
        self.settings = settings
        self.base_url = settings.keycloak_internal_url.rstrip("/")
        self.realm_path = f"/admin/realms/{quote(settings.keycloak_realm, safe='')}"

    def _client_secret(self) -> str:
        try:
            secret = Path(self.settings.registration_client_secret_file).read_text().strip()
        except OSError as error:
            raise KeycloakAdminUnavailable("Account registration is temporarily unavailable.") from error
        if not secret:
            raise KeycloakAdminUnavailable("Account registration is temporarily unavailable.")
        return secret

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        try:
            response = await client.post(
                f"{self.base_url}/realms/{quote(self.settings.keycloak_realm, safe='')}"
                "/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.registration_client_id,
                    "client_secret": self._client_secret(),
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise KeycloakAdminUnavailable("Account registration is temporarily unavailable.") from error

    async def _users(
        self, client: httpx.AsyncClient, token: str, *, username: str | None = None, email: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"exact": "true", "max": "2"}
        if username is not None:
            params["username"] = username
        if email is not None:
            params["email"] = email
        response = await client.get(
            f"{self.base_url}{self.realm_path}/users",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def account_exists(self, username: str, email: str) -> bool:
        timeout = httpx.Timeout(8.0, connect=3.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                token = await self._access_token(client)
                by_username = await self._users(client, token, username=username)
                by_email = await self._users(client, token, email=email)
                return bool(by_username or by_email)
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise KeycloakAdminUnavailable("Account registration is temporarily unavailable.") from error

    async def provision_verified_user(self, account: dict[str, str], password: str) -> None:
        timeout = httpx.Timeout(8.0, connect=3.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                token = await self._access_token(client)
                by_username = await self._users(client, token, username=account["username"])
                by_email = await self._users(client, token, email=account["email"])
                matches = {user["id"]: user for user in by_username + by_email}
                target = None
                if matches:
                    if len(matches) != 1:
                        raise DuplicateKeycloakAccount()
                    candidate = next(iter(matches.values()))
                    same_user = (
                        candidate.get("username", "").casefold() == account["username"].casefold()
                        and candidate.get("email", "").casefold() == account["email"].casefold()
                    )
                    if not same_user:
                        raise DuplicateKeycloakAccount()
                    # An earlier request may have created the user before its response was lost.
                    target = candidate["id"]

                payload = {
                    "username": account["username"],
                    "email": account["email"],
                    "firstName": account["first_name"],
                    "lastName": account["last_name"],
                    "emailVerified": True,
                    "enabled": True,
                    "requiredActions": [],
                }
                headers = {"Authorization": f"Bearer {token}"}
                if target:
                    response = await client.put(
                        f"{self.base_url}{self.realm_path}/users/{quote(target, safe='')}",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    response = await client.put(
                        f"{self.base_url}{self.realm_path}/users/{quote(target, safe='')}/reset-password",
                        headers=headers,
                        json={"type": "password", "value": password, "temporary": False},
                    )
                    response.raise_for_status()
                else:
                    response = await client.post(
                        f"{self.base_url}{self.realm_path}/users",
                        headers=headers,
                        json={
                            **payload,
                            "credentials": [{
                                "type": "password",
                                "value": password,
                                "temporary": False,
                            }],
                        },
                    )
                    if response.status_code == 409:
                        # Re-read and idempotently finish a create that raced another attempt.
                        return await self.provision_verified_user(account, password)
                    response.raise_for_status()
        except DuplicateKeycloakAccount:
            raise
        except (httpx.HTTPError, KeyError, ValueError) as error:
            raise KeycloakAdminUnavailable("Account activation could not be completed. Try again.") from error
