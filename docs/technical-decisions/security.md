# Security Decision

**Status: Security boundaries accepted; enforcement implementation pending.** The design separates identity (Keycloak), session handling (Next.js BFF), API authorization (FastAPI), and user-owned records. The current shell and health endpoints are not a secure multi-user product yet.

## Controls required

- OIDC authorization code with PKCE and server-side token storage.
- Secure HttpOnly SameSite cookies, CSRF protection for state-changing browser requests, session refresh/expiry, and logout.
- Backend JWT signature verification against Keycloak JWKS, issuer, audience, expiry, and role checks.
- Derive identity from verified claims; scope all conversations/documents/chunks to the owner.
- Validate upload size/type, normalize paths/names, and prevent unsafe parsing.
- Bind published ports to loopback, keep DBs on private networks, and keep secrets out of Git.
- Rate-limit expensive login/upload/chat operations and restrict CORS to known app origins.
- Treat retrieved text as untrusted prompt content; do not expose tools/secrets to it.

## Alternatives and trade-offs

A BFF with cookie sessions reduces browser token exposure but adds a server hop and CSRF concerns. A pure SPA with in-memory PKCE tokens can be simpler but has a different refresh and lifecycle trade-off. Custom password auth is rejected in favor of Keycloak's identity controls. Database row-level security could add defense in depth but increases connection/session configuration complexity; service-level owner filtering still needs integration tests.

## Risks

Weak issuer/audience checks can accept tokens minted for another client. Missing owner predicates can cause cross-user disclosure. Model prompt injection cannot be fully solved by prompt instructions. A compromised local PC remains outside the application's protection boundary.

## Verification plan

Add JWT tests for bad signature, wrong issuer/audience, expired token, and missing roles. Add cross-user API tests for every document/conversation operation. Test upload edge cases, cookie flags, CSRF, rate limits, and adversarial retrieved text. Do not claim controls as implemented until those tests pass.
