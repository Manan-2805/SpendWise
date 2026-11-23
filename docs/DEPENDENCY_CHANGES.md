# Dependency changes
Every package add, upgrade, or removal: package, version, why, approved by me (date).

## 2026-11-23 · SpendWise frontend foundation proposal

Status **approved for installation on 2026-11-23**, including the scoped minimatch override. Step 4 reverified all exact pins, engines, required peers, and the selected shadcn and AnimateIcons dependencies. A second lockfile-only resolution reconciled npm’s optional Ajv peer placement, then strict npm ci installed the pinned graph and npm audit reported zero vulnerabilities. The [implementation plan](plans/2026-11-23-frontend.md#dependency-verification) records the registry audit, one moderate transitive advisory, and the proposed scoped `minimatch@11.0.9` override approved for the scoped dependency. The build will lock the approved versions with npm and report any additional direct dependency before adding it. Existing Python dependencies are unaffected.

### Application dependencies

| Package | Proposed version | Reason |
|---|---|---|
| `react`, `react-dom` | `19.3.1` each | Render the Vite SPA |
| `react-router` | `8.5.2` | Browser routes, lazy screens and URL-backed filters |
| `@tanstack/react-query` | `5.108.4` | Cache server state, invalidate queries after mutations and coordinate eligible read retries |
| `openapi-fetch` | `0.17.0` | Typed same-origin requests with a shared cookie, refresh and runtime error policy |
| `react-hook-form` | `7.92.0` | Form state and per-field errors |
| `@hookform/resolvers` | `7.0.8` | Connect React Hook Form and Zod |
| `zod` | `4.6.7` | Validate form values, including decimal strings and password byte limits |
| `radix-ui` | `1.8.1` | Keyboard, focus and accessibility primitives behind the selected shadcn components |
| `cn` | `0.5.2` | Class merging used by the current shadcn registry |
| `tw-animate-css` | `1.4.0` | CSS animation primitives for shadcn component states |
| `next-themes` | `0.4.6` | Manage light and dark preference and theme the shadcn toast adapter |
| `sonner` | `2.0.8` | Toasts via the shadcn adapter |
| `recharts` | `3.8.0` | Charts at the version specified by the shadcn Radix chart registry |
| `react-is` | `19.3.1` | Recharts peer dependency, matched to React |
| `lucide-react` | `1.78.0` | Static interface icons and shadcn defaults |
| `motion` | `14.14.0` | Animate the selected status icons with reduced-motion handling |
| `@fontsource/barlow-condensed` | `5.3.0` | Self-host the approved display face, with the Latin weight needed for headings |
| `@fontsource-variable/instrument-sans` | `5.3.0` | Self-host the approved body and UI typeface |

Use the shadcn Radix registry for buttons, inputs, labels, alerts, dialogs, sheets, selects, tabs, dropdown menus, cards, badges, skeletons, tables, charts, and the Sonner adapter. The registry supplies source components. Copy only the AnimateIcons Loader and Check variants for pending and success feedback, using the existing `motion` dependency. The Ledger mark and favicon use project SVG assets.

### Development, build and test dependencies

| Package or tool | Proposed version | Reason |
|---|---|---|
| `create-vite` | `9.3.4` | One-time React TypeScript scaffold with automatic installation disabled |
| `vite` | `8.3.8` | Dev proxy on port 3000 with `strictPort` and a static production build |
| `@vitejs/plugin-react` | `6.3.0` | JSX transform and development Fast Refresh |
| `typescript` | `5.9.3` | Strict type checking within the published OpenAPI generator and ESLint compatibility ranges |
| `@types/node` | `22.20.5` | Types for the Node 22 tooling runtime |
| `@types/react`, `@types/react-dom` | `19.3.0` each | Types for React and browser rendering |
| `tailwindcss`, `@tailwindcss/vite` | `4.3.5` each | Compile the component utilities and Harbor Ink theme tokens |
| `shadcn` | `4.23.0` | Inspect and generate registry components and compile its shared Tailwind styles |
| `openapi-typescript` | `7.13.0` | Generate types from `docs/openapi.json` |
| `eslint`, `@eslint/js` | `10.15.0`, `10.0.1` | Lint and apply recommended flat-config rules |
| `typescript-eslint` | `8.73.0` | TypeScript lint rules, including a ban on explicit `any` |
| `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh` | `7.1.1`, `0.5.8` | Check hook usage and Fast Refresh exports |
| `globals` | `17.14.0` | Declare browser and Node globals in ESLint configuration |
| `vitest`, `jsdom` | `5.1.1`, `31.0.1` | Feature and DOM tests using the Vite configuration |
| `@testing-library/react`, `@testing-library/dom` | `16.3.3`, `10.4.2` | Verify UI through labels, roles and user-visible behavior |
| `@testing-library/jest-dom`, `@testing-library/user-event` | `8.0.0`, `14.6.13` | DOM assertions and realistic user input |
| `msw` | `3.0.7` | Mock the actual HTTP contract in feature tests |
| `@playwright/test` | `1.65.1` | Chromium login, add transaction and report flow |
| `@axe-core/playwright` | `4.14.0` | Accessibility checks in Playwright |

Use Node `22.23.5` and npm `10.9.9`, already available locally. The current Vite template proposes TypeScript 7 and Oxlint. Configure the approved TypeScript 5.9 and ESLint manifest before the first install. Use Node's built-in gzip support for the bundle budget check. Playwright supplies its matching browser runner transitively. Install only the Chromium browser for the planned flow.

### Container images for integration

| Image | Proposed tag | Reason |
|---|---|---|
| `node` | `22.23.5-alpine3.24` | Build the frontend with the same Node version used locally |
| `nginx` | `1.30.7-alpine3.24` | Serve the static bundle and proxy `/api/v1` with the public `Host` |
| `axllent/mailpit` | `v1.34.0` | Local SMTP inbox, enabled only through an optional development Compose profile |

Package versions and peer ranges were checked against the npm registry and the selected component registry. [Vite template and CLI](https://github.com/vitejs/vite/tree/main/packages/create-vite) · [shadcn class utility](https://ui.shadcn.com/docs/changelog/2026-09-cn) · [shadcn chart registry](https://ui.shadcn.com/r/styles/new-york-v4/chart.json) · [AnimateIcons](https://animateicons.in/) · [OpenAPI TypeScript npm metadata](https://registry.npmjs.org/openapi-typescript/7.13.0) · [Node image tags](https://github.com/docker-library/official-images/blob/master/library/node) · [nginx image tags](https://github.com/docker-library/official-images/blob/master/library/nginx) · [Mailpit release](https://github.com/axllent/mailpit/releases/tag/v1.34.0)

## 2026-11-22 — Targeted security upgrades

The user approved upgrading dependencies reported by pip-audit and compatibility dependencies. The first scan reported 99 advisory entries across 17 packages. The post-upgrade scan reported no known vulnerabilities in the installed dependencies. The local SpendWise package is outside the advisory feed.

| Package | Previous | Resolved | Reason |
|---|---|---|---|
| `anyio` | 4.13.0 | 4.14.2, 4.16.0 | Security advisory remediation |
| `authlib` | 1.7.2 | 1.9.10 | Security advisory remediation |
| `certifi` | 2026.5.20 | 2026.11.20 | Security advisory remediation |
| `cryptography` | 48.0.0 | 50.0.2 | Security advisory remediation |
| `distlib` | 0.4.0 | 0.4.4 | Compatibility with approved security upgrades |
| `dnspython` | 2.8.0 | 2.9.2 | Security advisory remediation |
| `filelock` | 3.29.0 | 4.3.0 | Security advisory remediation |
| `joserfc` | 1.6.8 | 1.8.0 | Security advisory remediation |
| `msgpack` | 1.1.2 | 1.2.4 | Security advisory remediation |
| `opentelemetry-api` | 1.42.1 | 1.45.2 | Security advisory remediation |
| `opentelemetry-instrumentation` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-asgi` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-fastapi` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-httpx` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-redis` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-sqlalchemy` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-sdk` | 1.42.1 | 1.45.2 | Compatibility with approved security upgrades |
| `opentelemetry-semantic-conventions` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-util-http` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `packaging` | 26.2 | 26.3 | Compatibility with approved security upgrades |
| `pip` | 26.1.2 | 26.3 | Security advisory remediation |
| `pydantic-settings` | 2.14.1 | 2.16.3 | Security advisory remediation |
| `pyjwt` | 2.13.0 | 2.15.1 | Security advisory remediation |
| `python-discovery` | 1.4.0 | 1.9.6 | Compatibility with approved security upgrades |
| `python-multipart` | 0.0.30 | 0.0.34 | Security advisory remediation |
| `starlette` | 1.2.1 | 1.10.0 | Security advisory remediation |
| `tornado` | 6.5.6 | 6.6.1 | Security advisory remediation |
| `urllib3` | 2.7.0 | 2.8.0 | Security advisory remediation |
| `virtualenv` | 21.4.2 | 21.15.12 | Security advisory remediation |
