# ADR-003: Use Keycloak and a server-side BFF session

- **Status:** Accepted design; implementation pending
- **Date:** 2026-11-10

## Context

The app requires registration, login, roles, token refresh, logout, and verified backend identity. Tokens must not be stored in localStorage. Numeric email OTP is requested.

## Problem statement

Choose an identity system and session boundary without implementing password and token lifecycle security inside the app.

## Decision

Use Keycloak OIDC authorization code flow with PKCE. The Next.js BFF will hold access/refresh tokens behind a Secure HttpOnly SameSite session cookie. FastAPI independently validates bearer JWTs.

## Alternatives considered

Auth0, Firebase Authentication, custom JWT/password code, and a client-only SPA token flow.

## Reasons for rejecting alternatives

Hosted Auth0/Firebase introduce cloud identity dependencies. Custom auth recreates security-sensitive lifecycle features. A pure SPA exposes tokens to browser JavaScript and complicates refresh/session policy compared with the BFF.

## Advantages

OIDC, account lifecycle, roles, and sessions are delegated to a dedicated identity service; backend authorization remains independent.

## Disadvantages

Keycloak consumes local resources and needs backup, realm, upgrade, and SMTP operations. Numeric OTP may require a Java extension because default verification is link-oriented.

## Risks and limitations

No realm import, OIDC callback, OTP extension, or FastAPI JWT verifier exists yet. Issuer/JWKS network addressing between host and containers needs careful configuration.

## Consequences

Authentication features must test code/link behavior, cookie security, refresh, JWKS rotation, and token claims. See [authentication.md](../authentication.md).

## Conditions for revisiting

Revisit if self-hosting identity is too costly, the product permits an external identity provider, or the OTP requirement changes.
