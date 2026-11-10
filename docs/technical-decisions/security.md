# Security Decision

**Status: Keycloak browser login and JWT verification implemented; full product authorization remains pending.** The design separates identity (Keycloak), in-memory browser token handling (`keycloak-js`), API authorization (FastAPI), and future user-owned records. Document/conversation ownership is not yet implemented.

## Controls required

- OIDC authorization code with PKCE S256 using a public client.
- Keep access/refresh tokens in memory only, refresh before expiry, and handle refresh failure by clearing the local session.
- Use hosted Keycloak login/registration pages; never collect passwords in the app.
- Backend JWT signature verification against Keycloak JWKS, issuer, audience, expiry, and role checks.
- Derive identity from verified claims; scope all conversations/documents/chunks to the owner.
- Validate upload size/type, normalize paths/names, and prevent unsafe parsing.
- Bind published ports to loopback, keep DBs on private networks, and keep secrets out of Git.
- Rate-limit expensive login/upload/chat operations and restrict CORS to known app origins.
- Treat retrieved text as untrusted prompt content; do not expose tools/secrets to it.

## Alternatives and trade-offs

A BFF with cookie sessions reduces JavaScript access to tokens but adds a server hop and CSRF concerns. The chosen SPA holds tokens in memory, avoids browser storage, and directly sends bearer tokens to FastAPI; this has greater XSS exposure than a BFF. Custom password auth is rejected in favor of Keycloak's identity controls. Database row-level security could add defense in depth but increases connection/session configuration complexity; service-level owner filtering still needs integration tests.

## Risks

Weak issuer/audience checks can accept tokens minted for another client. Missing owner predicates can cause cross-user disclosure. Model prompt injection cannot be fully solved by prompt instructions. A compromised local PC remains outside the application's protection boundary.

## Verification plan

JWT tests cover missing/invalid/expired tokens, valid claims, and wrong authorized client. Add tests for signature/issuer/audience failures, JWKS key rotation, and future cross-user document/conversation operations. Test upload edge cases, rate limits, and adversarial retrieved text. Do not claim controls as implemented until those tests pass.
