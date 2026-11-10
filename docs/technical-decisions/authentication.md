# Authentication Decision

**Status: Keycloak public-client login, logout, verified-email gating, and backend JWT checks implemented.** Use self-hosted Keycloak as the OIDC provider and `keycloak-js` as a public browser client. FastAPI independently verifies access JWTs using Keycloak JWKS and requires the signed `email_verified: true` claim for protected routes.

## Comparison

- **Keycloak:** self-hosted OIDC, roles, account flows, and administration. Good for local control and avoiding identity SaaS; costs memory, upgrades, realm configuration, and extension maintenance.
- **Auth0:** mature managed identity with low self-hosted operations. Better when cloud identity and a paid service are acceptable; it depends on an external service and does not match the strict local deployment preference.
- **Firebase Authentication:** convenient hosted identity and client SDK. Better for products already built around Firebase; less aligned with a self-hosted OIDC boundary and local-first operation.
- **Custom JWT authentication:** maximum control but requires secure password storage, recovery, email verification, session rotation, key management, brute-force defenses, and ongoing security review. It duplicates mature identity-provider responsibilities.

## Why Keycloak and a public client

Keycloak supplies OAuth/OIDC, user lifecycle, roles, sessions, and password recovery. The browser client uses Authorization Code Flow with PKCE S256; the public client has no secret. `keycloak-js` keeps access and refresh tokens in memory, refreshes them before expiry, and does not persist them in localStorage or sessionStorage. FastAPI validates signatures and claims independently. This is simpler than a BFF for this local app, but JavaScript executing in the page can access the in-memory token, so XSS defenses remain important. A BFF is preferable if that exposure is unacceptable.

## Numeric OTP trade-off

Keycloak's usual email verification action is link based. A numeric OTP requirement may need a custom authenticator/required-action extension. It introduces Java build/upgrade work and must enforce expiry, attempt limits, and resend throttling. Accepting verification links would materially reduce custom maintenance.

## Failure behavior and risks

After a valid access token is issued, FastAPI verifies using cached JWKS; JWKS fetch uses the container-internal Keycloak URL while the token issuer is checked against the browser-visible issuer. Login, refresh, logout, and email verification depend on Keycloak. The API validates RS256 signature, `iss`, `exp`, `sub`, and `azp` against `local-ai-frontend`; an optional audience can be required after an audience mapper is configured. It returns 403 unless `email_verified` is exactly `true`. Health routes remain public. Key rotation and issuer/client configuration errors can reject valid requests or, if validation is weakened, admit forged tokens.

## Email verification and SMTP

The `local-ai` realm enables registration, requires Keycloak's `VERIFY_EMAIL` required action, and sets `verifyEmail=true`. The frontend keeps users with a missing or false `email_verified` claim on a verification screen. All protected backend routes must depend on `get_email_verified_claims`, which first performs normal signature and issuer validation and then requires the claim to be true.

For local development, Keycloak sends mail through Mailpit at `mailpit:1025` on the shared Docker `smtp` network. The sender is `no-reply@local-ai.local`; SMTP authentication, SSL, and STARTTLS are disabled. Mailpit captures messages at [http://localhost:8025](http://localhost:8025); this is local capture, not delivery to an external mailbox. A versioned realm import configures new databases, and the `keycloak-config` startup job applies the same settings to an already persisted realm. The public `local-ai-frontend` client stays secret-free and uses PKCE S256.

For production, replace Mailpit with an SMTP provider and configure its host, port, sender address, TLS mode, authentication mode, username, and password using deployment secrets. Store SMTP credentials only in Keycloak's server-side configuration or a secret manager, never in frontend environment variables or browser code. Configure the provider's permitted sender/domain and test verification links against the production public hostname before opening registration.

## Revisit when

Reconsider if self-hosting identity becomes too costly, the local-only requirement changes, or browser-side tokens become unacceptable. Implementation references: [frontend/app/providers.tsx](../../frontend/app/providers.tsx), [backend/app/auth/keycloak.py](../../backend/app/auth/keycloak.py), and [backend/app/api/auth.py](../../backend/app/api/auth.py). Numeric email OTP remains separate and is not implemented here.
