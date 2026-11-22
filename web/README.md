# CodeTether Web

CodeTether's web application combines the product dashboard, public website, authentication, billing, and server-side API routes. This directory was previously named `marketing-site`.

The app uses Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, and Auth.js/NextAuth with Keycloak. It connects to CodeTether backend services for agent execution and platform data.

## Application structure

| Path | Purpose |
| --- | --- |
| `src/app/(dashboard)/` | Product dashboard: workspaces, tasks, sessions, workers, workflows, integrations, billing, and settings |
| `src/app/(auth)/` | Authentication pages |
| `src/app/(main)/` | Public website and landing pages |
| `src/app/api/` | Next.js server-side API routes |
| `src/auth.ts`, `src/middleware.ts` | Authentication configuration and request middleware |
| `src/components/` | Shared UI components |
| `src/hooks/`, `src/lib/` | Hooks, API clients, and application logic |
| `src/lib/api/generated/` | Generated OpenAPI client |
| `src/content/`, `src/styles/`, `public/` | Site content, styles, and static assets |
| `tests/`, `e2e/` | Regression and browser tests |

## Local development

Use Node.js 22 to match the [Docker build](Dockerfile), and npm. From the repository root:

```bash
cd web
npm ci
```

Create `web/.env.local` with configuration for your development backend and Keycloak client. Keep secrets out of source control. Check for overrides in `.env.development.local` if the app uses unexpected settings.

The development script serves **https://localhost:3001** using webpack and expects these local certificate files:

- `certs/localhost.pem`
- `certs/localhost-key.pem`

If you use `mkcert`, generate them from `web/`:

```bash
mkdir -p certs
mkcert -install
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
npm run dev
```

Open **https://localhost:3001**. Run subsequent npm commands in `web/`.

### Environment configuration

| Variable | Purpose |
| --- | --- |
| `NEXTAUTH_URL` | External web origin; use `https://localhost:3001` with the default development script |
| `AUTH_SECRET` | Auth.js session secret; generate a local value with `openssl rand -base64 32` |
| `KEYCLOAK_ISSUER` | Full realm issuer URL, such as `https://your-keycloak.example/realms/your-realm` |
| `KEYCLOAK_CLIENT_ID` | Registered Keycloak client ID; defaults to `a2a-monitor` |
| `KEYCLOAK_PUBLIC_CLIENT` | `true` for a public client, or `false` for a confidential client |
| `KEYCLOAK_CLIENT_SECRET` | Required for a confidential client |
| `NEXT_PUBLIC_API_URL` | Browser-facing API base URL; must be reachable by the browser |
| `API_URL` | Server-side backend URL used by authentication-related backend calls |
| `A2A_API_BACKEND` | Backend origin for `/api/v1/*` and `/api/tenant/*` rewrites |
| `COGNITION_API_BACKEND` | Backend origin for `/api/cognition/*` and `/api/swarm/*` rewrites |

Instead of `KEYCLOAK_ISSUER`, you can set `KEYCLOAK_URL` and `KEYCLOAK_REALM`; the issuer is then derived as `<KEYCLOAK_URL>/realms/<KEYCLOAK_REALM>`. See [authentication configuration](src/auth.ts) for supported aliases and defaults.

The rewrite variables are optional, but the corresponding proxies are disabled when unset. Configure them before starting or building the app. See [next.config.js](next.config.js) for the exact routing rules. Variables prefixed with `NEXT_PUBLIC_` are exposed to the browser and must not contain secrets. Individual integrations may require additional service-specific configuration.

### Keycloak login

Configure your development Keycloak client with the redirect URI:

```text
https://localhost:3001/api/auth/callback/keycloak
```

Set its Web Origin to `https://localhost:3001`. If you access the app through another hostname or port, update `NEXTAUTH_URL` and the client's allowed redirect URI and origin to match.

For public clients, set `KEYCLOAK_PUBLIC_CLIENT=true` and omit the client secret. For confidential clients, set `KEYCLOAK_PUBLIC_CLIENT=false` and provide `KEYCLOAK_CLIENT_SECRET`.

- `Invalid parameter: redirect_uri`: check the callback scheme, hostname, port, and path against the client's allowlist.
- `unauthorized_client` or `Invalid client credentials`: check the client ID, secret, and public/confidential mode.

Tenant signup and SSO also require the shared callback to be allowed by the tenant's client. See [authentication rollout notes](UI_VALIDATION.md).

## Validation

```bash
npm run lint
npm run test:auth
npm run test:ui
npm run test:voice
npx tsc --noEmit --incremental false
```

`test:auth` covers authentication helpers and callback flows. `test:ui` runs the configured Jest projects for dashboard navigation, settings/billing, task and session resilience, model selection, workspace home, and signup/checkout. `test:voice` runs the separate voice suite.

Browser tests use Playwright. Start the target application separately; the Playwright configuration does not start a development server. Set `BASE_URL` explicitly because its default is `https://codetether.run`:

```bash
npx playwright install chromium
BASE_URL=https://localhost:3001 npm run test:e2e
```

The browser must trust your development certificate. Use `npm run test:e2e:ui` or `npm run test:e2e:headed` with the same `BASE_URL` for interactive runs. See [UI validation notes](UI_VALIDATION.md) and [signup/checkout tests](tests/README.signup-checkout.md) for suite-specific setup and scope.

## API client generation

Regenerate the client from a running backend's OpenAPI schema:

```bash
# Defaults to https://api.codetether.run/openapi.json
npm run generate:api

# Uses http://localhost:8001/openapi.json
npm run generate:api:local

# Choose another schema endpoint
OPENAPI_URL=https://your-api.example/openapi.json npm run generate:api
```

The generator writes to `src/lib/api/generated/`. Make API changes in the backend schema and regenerate the client rather than editing generated files. Configuration lives in [openapi-ts.config.ts](openapi-ts.config.ts). Protobuf client output is configured separately in [buf.gen.yaml](../specification/grpc/buf.gen.yaml).

## Production build and deployment

```bash
npm run build
npm run start
```

The production server defaults to port 3000; set its public authentication origin and backend configuration for the target environment. Next.js is configured to emit standalone output for the container build.

The [Dockerfile](Dockerfile) installs dependencies, runs the UI and authentication suites, builds the app, and packages the standalone server. To build from the repository root:

```bash
docker build -t codetether-web ./web
```

For the existing image promotion workflow and deployment configuration, see [GitOps promotion](../docs/marketing-gitops-promotion.md).

## UI licensing

The UI incorporates the Pocket template and components from Tailwind Plus. See [LICENSE.md](LICENSE.md) for the applicable Tailwind Plus license terms.
