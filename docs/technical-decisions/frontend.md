# Frontend Framework Decision

**Status: Accepted; authentication UI is implemented, live Keycloak flow pending runtime verification.** The code uses Next.js App Router with React, TypeScript, CSS Modules/standard CSS, and a client-side `keycloak-js` provider.

## Selected stack

- **React** renders the component tree and manages interactive parts of the chat interface.
- **Next.js App Router** supplies application routing, server-rendered shell, and the standalone production server.
- **TypeScript** adds static checks for UI, API response, and session types.
- **CSS Modules and standard CSS** keep styles scoped without Tailwind, as required.

The current scaffold is in [frontend/app](../../frontend/app), configured by [package.json](../../frontend/package.json), and built through [frontend/Dockerfile](../../frontend/Dockerfile).

## Alternatives considered

### React alone

Plain React with Vite is lighter and simpler for a client-only single-page app. It would require separately choosing a router and deployment server. Next.js is retained because the requested stack specifies it and its standalone output is already part of the deployment. Since the selected authentication client is browser-based, server-side token handling is not the reason for choosing Next.js.

### Vue

Vue provides a cohesive component model and can be easier for teams already experienced with its templates and reactivity. The project specifically requires React/Next.js, and adopting Vue would remove that alignment without solving a unique requirement better.

### Angular

Angular includes a broad batteries-included application framework, DI, and established enterprise patterns. It can be a good choice for a large team with Angular expertise; for this small local product, its conventions and bundle/runtime footprint add more framework than needed.

## Benefits

- App Router combines routing and server-rendered pages with interactive React components.
- App Router provides a maintainable page/layout structure for the protected workspace.
- TypeScript supports shared, explicit data contracts.
- CSS Modules satisfy the no-Tailwind constraint and scope component styles.

## Costs and limits

- Next.js introduces server/client component boundaries and version-specific caching/runtime behavior.
- The current public-client flow keeps tokens in memory, where page JavaScript can access them; a BFF would reduce that exposure at the cost of server-side session and CSRF work.
- SSR alone does not make a route private; server session checks and backend authorization are still required.
- React and Next.js package updates need active maintenance.

## SSR trade-off

Server rendering can send initial HTML before browser JavaScript has loaded. It does not make local inference faster, and this local authenticated app does not depend on public search indexing. Auth state is initialized in the browser by `keycloak-js`; server rendering must not assume that a browser token exists.

## Revisit when

Reconsider the framework if the product becomes a packaged desktop application, if server rendering causes resource or operational issues, or if team skills and deployment constraints change. The original requirements currently favor Next.js.
