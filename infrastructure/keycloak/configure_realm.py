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
    realm["registrationAllowed"] = True
    realm["verifyEmail"] = True
    realm["smtpServer"] = {
        "host": "mailpit",
        "port": "1025",
        "from": "no-reply@local-ai.local",
        "fromDisplayName": "Local AI Platform",
        "ssl": "false",
        "starttls": "false",
        "auth": "false",
    }
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
    print(f"Configured email verification and Mailpit for realm {REALM}.")


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
    smtp = realm.get("smtpServer") or {}
    client = clients[0] if clients else {}
    checks = {
        "registration enabled": realm.get("registrationAllowed") is True,
        "email verification required": realm.get("verifyEmail") is True,
        "VERIFY_EMAIL action enabled by default": action.get("enabled") is True
        and action.get("defaultAction") is True,
        "Mailpit SMTP configured": smtp.get("host") == "mailpit"
        and smtp.get("port") == "1025"
        and smtp.get("from") == "no-reply@local-ai.local"
        and smtp.get("ssl") == "false"
        and smtp.get("starttls") == "false"
        and smtp.get("auth") == "false",
        "public client uses standard flow and PKCE S256": client.get("publicClient") is True
        and client.get("standardFlowEnabled") is True
        and client.get("attributes", {}).get("pkce.code.challenge.method") == "S256",
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
