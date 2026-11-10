from typing import Any

from fastapi import APIRouter, Depends

from app.auth.keycloak import get_current_claims
from app.schemas.auth import AuthenticatedUser

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.get("/me", response_model=AuthenticatedUser)
def authenticated_user(claims: dict[str, Any] = Depends(get_current_claims)) -> AuthenticatedUser:
    """Return identity and realm roles from a verified Keycloak access token."""
    return AuthenticatedUser.from_claims(claims)
