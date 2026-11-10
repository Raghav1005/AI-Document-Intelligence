# ADR-001: Use Next.js App Router for the frontend and BFF

- **Status:** Accepted for the UI foundation
- **Date:** 2026-11-10

## Context

The product requires a responsive React interface, OIDC login, and secure server-side session handling without storing tokens in local storage. The current scaffold uses Next.js App Router, React, TypeScript, and standard CSS/CSS Modules.

## Problem statement

Choose a frontend framework that supports the required interface and a server boundary for OIDC callbacks and future API proxying.

## Decision

Use Next.js App Router and React with TypeScript. Use CSS Modules/standard CSS and do not use Tailwind.

## Alternatives considered

Plain React with Vite, Vue, and Angular.

## Reasons for rejecting alternatives

Vite is a good fit for client-only UI but would require an additional BFF/server. Vue conflicts with the specified React stack. Angular offers a larger built-in framework than this MVP requires.

## Advantages

Server rendering and route handlers provide a place for OIDC callback and server-held tokens. App Router supplies route structure, while React covers the interactive chat interface.

## Disadvantages

The application must manage server/client component boundaries and Next.js upgrade behavior. The BFF introduces a hop and additional session/CSRF responsibility.

## Risks and limitations

The present UI is a scaffold; session security and streaming proxy behavior are not yet implemented or tested. SSR does not replace backend access control.

## Consequences

Frontend and BFF code will live in one Next.js service. Token refresh and session logic must remain server-side. See [frontend.md](../frontend.md) and [frontend/app/page.tsx](../../../frontend/app/page.tsx).

## Conditions for revisiting

Revisit if a separate BFF is introduced, deployment changes to a packaged desktop app, or the Next server becomes a resource/maintenance burden.
