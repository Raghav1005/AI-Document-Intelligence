"""Idempotently apply local email verification and Mailpit settings to Keycloak."""

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "local-ai")
REGISTRATION_CLIENT_ID = os.getenv(
    "KEYCLOAK_REGISTRATION_CLIENT_ID", "local-ai-registration"
)
REGISTRATION_SECRET_PATH = os.getenv(
    "REGISTRATION_SECRET_PATH",
    "/run/secrets/registration/keycloak-client-secret",
)
ADMIN = os.environ["KEYCLOAK_ADMIN"]
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]


def request_json(path: str, *, method: str = "GET", payload: object = None, token: str = ""):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=8) as response:
        if response.status == 204 or not response.readable():
            return None
        response_body = response.read()
        return json.loads(response_body) if response_body else None


def admin_token() -> str:
    form = urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN,
            "password": ADMIN_PASSWORD,
        }
    ).encode()
    request = Request(
        f"{BASE_URL}/realms/master/protocol/openid-connect/token",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read())["access_token"]


def registration_client(token: str) -> dict:
    realm_path = f"/admin/realms/{REALM}"
    clients = request_json(
        f"{realm_path}/clients?clientId={REGISTRATION_CLIENT_ID}", token=token
    )
    if not clients:
        body = {
            "clientId": REGISTRATION_CLIENT_ID,
            "name": "Local AI Registration API",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "clientAuthenticatorType": "client-secret",
            "standardFlowEnabled": False,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": True,
        }
        request_json(f"{realm_path}/clients", method="POST", payload=body, token=token)
        clients = request_json(
            f"{realm_path}/clients?clientId={REGISTRATION_CLIENT_ID}", token=token
        )
    if not clients:
        raise RuntimeError("The backend registration client could not be configured.")

    client = clients[0]
    client.update({
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": False,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": True,
    })
    request_json(
        f"{realm_path}/clients/{client['id']}",
        method="PUT",
        payload=client,
        token=token,
    )

    # Keycloak 26.8+ requires an explicit Admin API audience on service tokens.
    client_scopes = request_json(f"{realm_path}/client-scopes", token=token)
    admin_api_scope = next(
        (scope for scope in client_scopes if scope.get("name") == "kc-admin-api"),
        None,
    )
    if not admin_api_scope:
        raise RuntimeError("Keycloak's kc-admin-api client scope is unavailable.")
    default_scopes = request_json(
        f"{realm_path}/clients/{client['id']}/default-client-scopes", token=token
    ) or []
    if admin_api_scope["id"] not in {scope.get("id") for scope in default_scopes}:
        request_json(
            f"{realm_path}/clients/{client['id']}/default-client-scopes/{admin_api_scope['id']}",
            method="PUT",
            token=token,
        )

    management_clients = request_json(
        f"{realm_path}/clients?clientId=realm-management", token=token
    )
    if not management_clients:
        raise RuntimeError("Keycloak realm-management client is unavailable.")
    management_id = management_clients[0]["id"]
    account = request_json(
        f"{realm_path}/clients/{client['id']}/service-account-user", token=token
    )
    roles = [
        request_json(f"{realm_path}/clients/{management_id}/roles/{role}", token=token)
        for role in ("manage-users", "query-users")
    ]
    mappings_path = (
        f"{realm_path}/users/{account['id']}/role-mappings/clients/{management_id}"
    )
    current = request_json(mappings_path, token=token) or []
    current_ids = {role["id"] for role in current}
    missing = [role for role in roles if role["id"] not in current_ids]
    if missing:
        request_json(mappings_path, method="POST", payload=missing, token=token)

    secret = request_json(
        f"{realm_path}/clients/{client['id']}/client-secret", token=token
    )["value"]
    os.makedirs(os.path.dirname(REGISTRATION_SECRET_PATH), exist_ok=True)
    temporary_path = REGISTRATION_SECRET_PATH + ".tmp"
    descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(secret)
        secret_file.flush()
        os.fsync(secret_file.fileno())
    os.replace(temporary_path, REGISTRATION_SECRET_PATH)
    os.chmod(REGISTRATION_SECRET_PATH, 0o600)
    return client


def configure() -> None:
    for attempt in range(30):
        try:
            token = admin_token()
            break
        except (HTTPError, URLError, TimeoutError):
            if attempt == 29:
                raise
            time.sleep(2)

    realm_path = f"/admin/realms/{REALM}"
    realm = request_json(realm_path, token=token)
    realm["registrationAllowed"] = False
    realm["resetPasswordAllowed"] = True
    realm["verifyEmail"] = True
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    if bool(smtp_username) != bool(smtp_password):
        raise RuntimeError("Provide both SMTP_USERNAME and SMTP_PASSWORD, or neither.")
    if os.getenv("SMTP_USE_TLS", "false").lower() == "true" and os.getenv(
        "SMTP_USE_SSL", "false"
    ).lower() == "true":
        raise RuntimeError("Configure either SMTP STARTTLS or SSL, not both.")
    smtp = {
        "host": os.getenv("SMTP_HOST", "mailpit"),
        "port": os.getenv("SMTP_PORT", "1025"),
        "from": os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_FROM", "no-reply@local-ai.local")),
        "fromDisplayName": os.getenv("SMTP_FROM_NAME", "Local AI"),
        "ssl": os.getenv("SMTP_USE_SSL", "false").lower(),
        "starttls": os.getenv("SMTP_USE_TLS", "false").lower(),
        "auth": "true" if smtp_username else "false",
    }
    if smtp_username:
        smtp["user"] = smtp_username
        smtp["password"] = smtp_password
    else:
        smtp.pop("user", None)
        smtp.pop("password", None)
    realm["smtpServer"] = smtp
    request_json(realm_path, method="PUT", payload=realm, token=token)

    required_action_path = (
        f"{realm_path}/authentication/required-actions/VERIFY_EMAIL"
    )
    required_action = request_json(required_action_path, token=token)
    required_action["enabled"] = True
    required_action["defaultAction"] = True
    request_json(required_action_path, method="PUT", payload=required_action, token=token)

    clients = request_json(
        f"{realm_path}/clients?clientId=local-ai-frontend", token=token
    )
    if not clients:
        raise RuntimeError("The imported local-ai-frontend client is missing.")
    client = clients[0]
    client["publicClient"] = True
    client["standardFlowEnabled"] = True
    client["implicitFlowEnabled"] = False
    client["directAccessGrantsEnabled"] = False
    client["serviceAccountsEnabled"] = False
    attributes = client.get("attributes") or {}
    attributes["pkce.code.challenge.method"] = "S256"
    client["attributes"] = attributes
    client["redirectUris"] = sorted(
        set(client.get("redirectUris", [])) | {"http://localhost:3000/*"}
    )
    client["webOrigins"] = sorted(
        set(client.get("webOrigins", [])) | {"http://localhost:3000"}
    )
    request_json(
        f"{realm_path}/clients/{client['id']}",
        method="PUT",
        payload=client,
        token=token,
    )
    registration_client(token)
    print(f"Configured private OTP registration and Mailpit for realm {REALM}.")


def verify() -> None:
    token = admin_token()
    realm = request_json(f"/admin/realms/{REALM}", token=token)
    action = request_json(
        f"/admin/realms/{REALM}/authentication/required-actions/VERIFY_EMAIL",
        token=token,
    )
    clients = request_json(
        f"/admin/realms/{REALM}/clients?clientId=local-ai-frontend", token=token
    )
    registration_clients = request_json(
        f"/admin/realms/{REALM}/clients?clientId={REGISTRATION_CLIENT_ID}", token=token
    )
    registration_client_scopes = []
    if registration_clients:
        registration_client_scopes = request_json(
            f"/admin/realms/{REALM}/clients/{registration_clients[0]['id']}/default-client-scopes",
            token=token,
        ) or []
    role_mapping_ok = False
    if registration_clients:
        registration_client_data = registration_clients[0]
        account = request_json(
            f"/admin/realms/{REALM}/clients/{registration_client_data['id']}/service-account-user",
            token=token,
        )
        management_clients = request_json(
            f"/admin/realms/{REALM}/clients?clientId=realm-management", token=token
        )
        if management_clients:
            management_id = management_clients[0]["id"]
            role_mappings = request_json(
                f"/admin/realms/{REALM}/users/{account['id']}/role-mappings/clients/{management_id}",
                token=token,
            ) or []
            role_mapping_ok = {role.get("name") for role in role_mappings} == {
                "manage-users", "query-users"
            }
    smtp = realm.get("smtpServer") or {}
    client = clients[0] if clients else {}
    expected_smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    expected_smtp = {
        "host": os.getenv("SMTP_HOST", "mailpit"),
        "port": os.getenv("SMTP_PORT", "1025"),
        "from": os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_FROM", "no-reply@local-ai.local")),
        "fromDisplayName": os.getenv("SMTP_FROM_NAME", "Local AI"),
        "ssl": os.getenv("SMTP_USE_SSL", "false").lower(),
        "starttls": os.getenv("SMTP_USE_TLS", "false").lower(),
        "auth": "true" if expected_smtp_username else "false",
    }
    smtp_ok = all(smtp.get(key) == value for key, value in expected_smtp.items())
    if expected_smtp_username:
        smtp_ok = smtp_ok and smtp.get("user") == expected_smtp_username and bool(smtp.get("password"))
    checks = {
        "Keycloak public registration disabled": realm.get("registrationAllowed") is False,
        "Keycloak password reset enabled": realm.get("resetPasswordAllowed") is True,
        "email verification required": realm.get("verifyEmail") is True,
        "VERIFY_EMAIL action enabled by default": action.get("enabled") is True
        and action.get("defaultAction") is True,
        "Configured SMTP provider is set": smtp_ok,
        "public client uses standard flow and PKCE S256": client.get("publicClient") is True
        and client.get("standardFlowEnabled") is True
        and client.get("attributes", {}).get("pkce.code.challenge.method") == "S256",
        "backend registration client is confidential": bool(registration_clients)
        and registration_clients[0].get("publicClient") is False
        and registration_clients[0].get("serviceAccountsEnabled") is True
        and registration_clients[0].get("clientAuthenticatorType") == "client-secret"
        and os.path.isfile(REGISTRATION_SECRET_PATH),
        "backend registration client has the Keycloak 26.8 Admin API scope": any(
            scope.get("name") == "kc-admin-api" for scope in registration_client_scopes
        ),
        "backend service account has only user-management lookup roles": role_mapping_ok,
    }
    for label, passed in checks.items():
        print(f"{label}: {'OK' if passed else 'FAILED'}")
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    if "--verify" in sys.argv[1:]:
        verify()
    else:
        configure()
