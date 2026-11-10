# ADR-001: Use Next.js App Router for the frontend

- **Status:** Accepted for the UI foundation
- **Date:** 2026-11-10

## Context

The product requires a responsive React interface, OIDC login, standalone deployment, and typed API integration. The current code uses Next.js App Router, React, TypeScript, and standard CSS/CSS Modules; auth uses a browser public client with in-memory tokens.

## Problem statement

Choose a frontend framework that supports the required interface and standalone deployment.

## Decision

Use Next.js App Router and React with TypeScript. Use CSS Modules/standard CSS and do not use Tailwind. OIDC runs in the browser through `keycloak-js`; no client secret is bundled.

## Alternatives considered

Plain React with Vite, Vue, and Angular.

## Reasons for rejecting alternatives

Vite is a good fit for client-only UI but would require separately choosing a router/server. Vue conflicts with the specified React stack. Angular offers a larger built-in framework than this MVP requires.

## Advantages

Standalone output supports the requested container deployment, and App Router supplies route structure while React covers the interactive interface.

## Disadvantages

The application must manage server/client component boundaries and Next.js upgrade behavior. The browser public-client flow exposes in-memory tokens to JavaScript executing in the page.

## Risks and limitations

In-memory tokens remain accessible to running page JavaScript; XSS remains a risk. Live login and session renewal still require runtime verification. SSR does not replace backend access control.

## Consequences

Frontend auth state lives in the client provider. FastAPI independently validates tokens. See [frontend.md](../frontend.md) and [frontend/app/page.tsx](../../../frontend/app/page.tsx).

## Conditions for revisiting

Revisit if deployment changes to a packaged desktop app or the Next server becomes a resource/maintenance burden.
