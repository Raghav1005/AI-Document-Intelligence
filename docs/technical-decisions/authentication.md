# Authentication Decision

**Status: Accepted design; implementation pending.** Use self-hosted Keycloak for OIDC identity and a Next.js BFF session. FastAPI independently verifies access JWTs using Keycloak JWKS. The session and token flow is designed but not yet implemented.

## Comparison

- **Keycloak:** self-hosted OIDC, roles, account flows, and administration. Good for local control and avoiding identity SaaS; costs memory, upgrades, realm configuration, and extension maintenance.
- **Auth0:** mature managed identity with low self-hosted operations. Better when cloud identity and a paid service are acceptable; it depends on an external service and does not match the strict local deployment preference.
- **Firebase Authentication:** convenient hosted identity and client SDK. Better for products already built around Firebase; less aligned with a self-hosted OIDC boundary and local-first operation.
- **Custom JWT authentication:** maximum control but requires secure password storage, recovery, email verification, session rotation, key management, brute-force defenses, and ongoing security review. It duplicates mature identity-provider responsibilities.

## Why Keycloak and BFF

Keycloak supplies OAuth/OIDC, user lifecycle, roles, sessions, and password recovery. The BFF stores tokens server-side behind an HttpOnly cookie; FastAPI still validates the access JWT itself. This avoids browser local storage and ensures the API does not trust frontend validation.

## Numeric OTP trade-off

Keycloak's usual email verification action is link based. A numeric OTP requirement may need a custom authenticator/required-action extension. It introduces Java build/upgrade work and must enforce expiry, attempt limits, and resend throttling. Accepting verification links would materially reduce custom maintenance.

## Failure behavior and risks

After a valid access token is issued, FastAPI can validate using cached JWKS until expiry/rotation policy requires Keycloak. Login, refresh, and logout depend on Keycloak. Key rotation and issuer/audience configuration errors can reject valid requests or, if validation is weakened, admit forged tokens. Use strict validation and tests.

## Revisit when

Reconsider if self-hosting identity becomes too costly, the local-only requirement changes, or the numeric OTP requirement is relaxed. Implementation references: [docker-compose.yml](../../docker-compose.yml), [backend/app/main.py](../../backend/app/main.py), and the planned Next.js BFF.
