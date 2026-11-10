from typing import Any

from pydantic import BaseModel, ConfigDict


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub: str
    username: str | None = None
    email: str | None = None
    roles: list[str]

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> "AuthenticatedUser":
        realm_access = claims.get("realm_access", {})
        realm_roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        return cls(
            sub=claims["sub"],
            username=claims.get("preferred_username"),
            email=claims.get("email"),
            roles=[role for role in realm_roles if isinstance(role, str)],
        )
