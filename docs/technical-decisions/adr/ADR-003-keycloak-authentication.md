# ADR-003: Use Keycloak with a public PKCE client

- **Status:** Accepted and implemented; live integration pending verification
- **Date:** 2026-11-10

## Context

The app requires registration, login, token refresh, logout, and independently verified backend identity. The configured client is public and has no client secret.

## Problem statement

Choose an identity provider and client flow without implementing passwords and account lifecycle security inside the application.

## Decision

Use Keycloak OIDC Authorization Code Flow with PKCE S256 through `keycloak-js`. Keep tokens in memory, refresh them before expiry, and send bearer access tokens to FastAPI. FastAPI verifies JWT signatures and claims independently.

## Alternatives considered

Auth0, Firebase Authentication, custom JWT/password code, and a Next.js BFF with server-side session cookies.

## Reasons for rejecting alternatives

Hosted Auth0/Firebase introduce cloud identity dependencies. Custom auth recreates security-sensitive lifecycle features. A BFF reduces JavaScript access to tokens but adds proxy, cookie, CSRF, and session infrastructure; the public SPA is simpler for this local deployment and does not persist tokens in browser storage.

## Advantages

OIDC, account lifecycle, roles, and sessions are delegated to a dedicated identity service; backend authorization remains independent. No client secret is shipped to the browser.

## Disadvantages

Keycloak consumes local resources and needs backup, realm, upgrade, and SMTP operations. In-memory tokens are accessible to running page JavaScript. Numeric OTP may require a Java extension because default verification is link-oriented.

## Risks and limitations

The provider and verifier are implemented and unit-tested, but live redirects/JWKS have not been verified with running containers. OTP remains out of scope. Public issuer and internal JWKS network addresses must stay consistent.

## Consequences

Verify login/registration redirects, refresh, logout, JWKS rotation, and token claims. See [authentication.md](../authentication.md).

## Conditions for revisiting

Revisit if self-hosting identity is too costly, the product permits an external identity provider, or browser-side token exposure becomes unacceptable.
