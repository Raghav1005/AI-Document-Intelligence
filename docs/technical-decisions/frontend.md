# Frontend Framework Decision

**Status: Accepted for the UI foundation.** The current code is a Next.js App Router scaffold with React, TypeScript, and CSS Modules/standard CSS; interactive authentication and chat behavior are not implemented yet.

## Selected stack

- **React** renders the component tree and manages interactive parts of the chat interface.
- **Next.js App Router** supplies server rendering, routing, server-side code for the planned BFF, and a production server.
- **TypeScript** adds static checks for UI, API response, and session types.
- **CSS Modules and standard CSS** keep styles scoped without Tailwind, as required.

The current scaffold is in [frontend/app](../../frontend/app), configured by [package.json](../../frontend/package.json), and built through [frontend/Dockerfile](../../frontend/Dockerfile).

## Alternatives considered

### React alone

Plain React with Vite is lighter and simpler for a client-only single-page app. It would require separate routing and a distinct BFF/server for secure server-side token storage. Since this application needs an OIDC callback and server-side session/token handling, Next.js provides a natural server boundary. If the application later becomes a desktop-only client with an independently hosted BFF, Vite could reduce framework overhead.

### Vue

Vue provides a cohesive component model and can be easier for teams already experienced with its templates and reactivity. The project specifically requires React/Next.js, and adopting Vue would remove that alignment without solving a unique requirement better.

### Angular

Angular includes a broad batteries-included application framework, DI, and established enterprise patterns. It can be a good choice for a large team with Angular expertise; for this small local product, its conventions and bundle/runtime footprint add more framework than needed.

## Benefits

- App Router combines routing and server-rendered pages with interactive React components.
- The server runtime can handle the OIDC callback and keep tokens out of browser local storage.
- TypeScript supports shared, explicit data contracts.
- CSS Modules satisfy the no-Tailwind constraint and scope component styles.

## Costs and limits

- Next.js introduces server/client component boundaries and version-specific caching/runtime behavior.
- The BFF adds a proxy hop and requires careful cookie, CSRF, and streaming behavior.
- SSR alone does not make a route private; server session checks and backend authorization are still required.
- React and Next.js package updates need active maintenance.

## SSR trade-off

Server rendering can send an initial HTML view before browser JavaScript has loaded and can make the OIDC callback/session boundary server-side. It does not make local inference faster, and this local authenticated app does not depend on public search indexing. Client-side rendering could be preferable for a static desktop shell; SSR is selected for the BFF and session boundary rather than SEO.

## Revisit when

Reconsider the framework if the product becomes a packaged desktop application with a separate BFF, if server rendering causes resource or operational issues, or if team skills and deployment constraints change. The original requirements currently favor Next.js.
