from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.keycloak import (
    KeycloakSettings,
    KeycloakTokenVerifier,
    get_token_verifier,
)
from app.main import app


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, object, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = KeycloakSettings(
        KEYCLOAK_ISSUER="http://localhost:8080/realms/local-ai",
        KEYCLOAK_INTERNAL_URL="http://keycloak:8080",
        KEYCLOAK_REALM="local-ai",
        KEYCLOAK_CLIENT_ID="local-ai-frontend",
    )
    verifier = KeycloakTokenVerifier(settings)
    verifier._signing_key = lambda _token: private_key.public_key()  # type: ignore[method-assign]
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    with TestClient(app) as client:
        yield client, private_key, settings

    app.dependency_overrides.clear()


def make_token(private_key: object, settings: KeycloakSettings, **overrides: object) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        "iss": settings.issuer,
        "sub": "user-123",
        "iat": now,
        "exp": now + timedelta(minutes=2),
        "azp": settings.client_id,
        "preferred_username": "raghav",
        "email": "raghav@example.test",
        "email_verified": True,
        "realm_access": {"roles": ["user"]},
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_missing_bearer_token_is_rejected(auth_client: tuple[TestClient, object, object]) -> None:
    client, _, _ = auth_client

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_jwt_is_rejected(auth_client: tuple[TestClient, object, object]) -> None:
    client, _, _ = auth_client

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


def test_expired_jwt_is_rejected(auth_client: tuple[TestClient, object, object]) -> None:
    client, private_key, settings = auth_client
    token = make_token(
        private_key,
        settings,
        exp=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_valid_jwt_returns_claim_identity(auth_client: tuple[TestClient, object, object]) -> None:
    client, private_key, settings = auth_client
    token = make_token(private_key, settings)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-123",
        "username": "raghav",
        "email": "raghav@example.test",
        "roles": ["user"],
    }


def test_unverified_email_is_forbidden(auth_client: tuple[TestClient, object, object]) -> None:
    client, private_key, settings = auth_client
    token = make_token(private_key, settings, email_verified=False)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Verify your email address before accessing the workspace."


def test_missing_email_verified_claim_is_forbidden(
    auth_client: tuple[TestClient, object, object],
) -> None:
    client, private_key, settings = auth_client
    claims = jwt.decode(
        make_token(private_key, settings),
        options={"verify_signature": False, "verify_exp": False},
    )
    claims.pop("email_verified")
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_health_endpoints_remain_public() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_wrong_authorized_client_is_rejected(
    auth_client: tuple[TestClient, object, object],
) -> None:
    client, private_key, settings = auth_client
    token = make_token(private_key, settings, azp="another-client")

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
