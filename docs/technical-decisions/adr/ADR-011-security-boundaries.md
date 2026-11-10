# ADR-011: Enforce identity and ownership at the API boundary

- **Status:** Accepted design; enforcement pending
- **Date:** 2026-11-10

## Context

Users must not access another user's documents, chunks, conversations, or messages. Uploaded content may contain prompt injection.

## Problem statement

Define security boundaries across browser, Keycloak, API, databases, and local models.

## Decision

Use a public Keycloak client with PKCE S256 and in-memory tokens, independent FastAPI JWT validation, and future owner-scoped backend queries derived from verified `sub`. Treat retrieved text as untrusted input and do not expose tools/secrets to it. Bind service ports to loopback and keep databases on private Compose networks.

## Alternatives considered

Frontend-only access checks, browser localStorage/sessionStorage tokens, custom password auth, and relying only on prompt instructions.

## Reasons for rejecting alternatives

Frontend checks can be bypassed. Persistent browser storage exposes tokens to scripts that execute later; in-memory tokens still have XSS exposure while the page runs. Custom passwords duplicate identity security. Prompt wording alone cannot reliably prevent injection.

## Advantages

Separates identity from API authorization and minimizes browser token exposure; ownership is enforced where data is accessed.

## Disadvantages

BFF would add cookie/CSRF/session responsibilities if selected later. Owner filters must be applied consistently; local computer compromise is outside the app boundary.

## Risks and limitations

JWT verification and CORS are implemented and unit-tested. Owner filters, rate limits, and upload validation remain future work; live JWKS retrieval is not verified yet.

## Consequences

Add negative authorization tests and security checks with each feature. See [security.md](../security.md).

## Conditions for revisiting

Revisit if deployment boundary changes, a different session pattern is introduced, or row-level security becomes appropriate as defense in depth.
