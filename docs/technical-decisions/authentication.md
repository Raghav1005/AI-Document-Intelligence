# Authentication Decision

**Status: Frontend integration and backend JWT verification implemented; live Keycloak flow not yet runtime-verified.** Use self-hosted Keycloak as the OIDC provider and `keycloak-js` as a public browser client. FastAPI independently verifies access JWTs using Keycloak JWKS.

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

After a valid access token is issued, FastAPI verifies using cached JWKS; JWKS fetch uses the container-internal Keycloak URL while the token issuer is checked against the browser-visible issuer. Login, refresh, and logout depend on Keycloak. The API validates `iss`, `exp`, signature, and `azp` against `local-ai-frontend`; an optional audience can be required after an audience mapper is configured. Key rotation and issuer/client configuration errors can reject valid requests or, if validation is weakened, admit forged tokens.

## Revisit when

Reconsider if self-hosting identity becomes too costly, the local-only requirement changes, or browser-side tokens become unacceptable. Implementation references: [frontend/app/providers.tsx](../../frontend/app/providers.tsx), [backend/app/auth/keycloak.py](../../backend/app/auth/keycloak.py), and [backend/app/api/auth.py](../../backend/app/api/auth.py). Numeric email OTP remains separate and is not implemented here.
