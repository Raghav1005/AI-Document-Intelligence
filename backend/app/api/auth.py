from typing import Any

from fastapi import APIRouter, Depends

from app.auth.keycloak import get_email_verified_claims
from app.schemas.auth import AuthenticatedUser

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.get("/me", response_model=AuthenticatedUser)
def authenticated_user(claims: dict[str, Any] = Depends(get_email_verified_claims)) -> AuthenticatedUser:
    """Return identity from a signed token after requiring verified email."""
    return AuthenticatedUser.from_claims(claims)
