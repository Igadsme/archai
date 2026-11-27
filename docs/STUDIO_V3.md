# ArchAI Studio V3 (Figma Make export → `apps/web`)

ArchAI Studio V3 is the official frontend. Its visual system comes from the Figma Make "ArchAI Studio V3" export: the dark graphite palette, technical typography, sidebar, topbar, status bar, panels, Explorer workbench, command palette, diagnostic console and responsive breakpoints. Everything it shows comes from the ArchAI FastAPI service. The export's sample data (`src/data.ts`) is not used.

## Framework decision

The Studio stays on **Next.js 16 (App Router) + React 19 + TypeScript**. The export was a Vite + React SPA with a `useState` view switcher; its components and stylesheet were moved into Next.js rather than replacing the framework:

| Export (Vite) | Studio (Next.js) | Why |
| --- | --- | --- |
| `useState<View>` view switcher in `App.tsx` | One App Router route per screen (`app/<route>/page.tsx`) with `StudioShell` in `app/layout.tsx` | Deep links, browser history, per-route titles, static prerendering |
| `@import url(fonts.googleapis.com…)` | `next/font/google` (Inter, JetBrains Mono) self-hosted at build time | The production CSP keeps `font-src 'self'` and no third-party origins |
| Tailwind v4 (Preflight only; no utility classes are used) | `app/studio/preflight.css` (vendored Preflight in `@layer base`) | Same reset, no new build dependency |
| `src/api/client.ts` stub that throws `BackendUnavailableError` | `app/lib/api.ts` typed client against the real API | See "API client" |
| Inline fixtures (`src/data.ts`, hard-coded nodes, GPU numbers, logs) | Live endpoints, plus explicit *Unavailable* / *not measured* states | No fabricated results |

The `ssr: false` dynamic import is used only for the Explorer workbench (`screens/ExplorerClient.tsx`): it restores tabs and panel sizes from `localStorage` and measures the canvas. All other screens prerender as static shells and fetch on the client.

## Files

| Export file | Studio file(s) |
| --- | --- |
| `src/index.css` | `app/studio/figma-v3.css` (verbatim, except: the font `@import`s are removed, `--sans`/`--mono` point at the `next/font` variables, sidebar selectors target `<a>`/`<select>`, and document-tab selectors also match `.doc-tab`) |
| (new) | `app/studio/studio.css`: states the prototype had no styles for (loading, load error, unavailable, offline, forms wired to the API, real-data charts, ArchAI operator colours, narrow-screen API-key popover) |
| `src/App.tsx` (shell) | `app/studio/StudioShell.tsx`, `app/studio/navigation.ts` |
| `src/App.tsx` (screens) | `app/screens/{Overview,Generator,SearchLab,Training,Pareto,Benchmarks,Experiments,System}.tsx` |
| `src/screens/Explorer.tsx` | `app/screens/Explorer.tsx`, `app/lib/architectureGraph.ts` (graph model from typed architecture data) |
| `src/screens/Registry.tsx` | `app/screens/Registry.tsx` |
| `src/components/CommandPalette.tsx` | `app/studio/CommandPalette.tsx` |
| `src/components/ErrorBoundary.tsx` | `app/studio/ErrorBoundary.tsx` (resets when the route changes) |
| `src/components/Icon.tsx` | `app/studio/Icon.tsx` (+ refresh, alert, key) |
| `src/components/ui.tsx` | `app/studio/ui.tsx` (+ `Loaded`, `Unavailable`, `ErrorList`, `EmptyState`, formatters) |
| `src/types.ts` | `app/lib/types.ts` (API response types) |
| `src/api/client.ts` | `app/lib/api.ts`, `app/lib/validators.ts`, `app/components/usePoll.ts` |
| `src/data.ts` | not migrated |

The previous Studio's `components/Shell.tsx`, `DagView.tsx`, `Scatter.tsx` and `app/styles.css` were removed. The previous Studio's form builders, Pareto math, results helpers and fixtures in `app/lib/` are reused unchanged.

## Screens and routes

| Screen | Route | Endpoints |
| --- | --- | --- |
| Research Overview | `/` | `/v1/architectures`, `/v1/searches`, `/v1/jobs`, `/v1/models`, `/v1/infrastructure/{workers,queue}`, `/v1/projects`, `/v1/research/results/nasbench201_cifar10_full_suite` |
| Neural Architecture Explorer | `/explorer` (`?id=`) | `/v1/architectures`, `/v1/architectures/{id}`, `POST /v1/architectures/validate`, `POST /v1/architectures`, `/v1/architectures/{id}/export?format=json\|pytorch`, `/v1/infrastructure/workers` |
| Architecture Generator | `/generator` | `POST /v1/architectures/generate`, `POST /v1/architectures/validate`, `POST /v1/architectures` |
| Autonomous Search Laboratory | `/search` (`?session=`) | `/v1/search/algorithms`, `POST /v1/searches`, `POST /v1/searches/{id}/start`, `POST /v1/searches/{id}/cancel`, `/v1/searches`, `/v1/searches/{id}`, `/v1/infrastructure/workers` |
| Training and GPU Monitoring | `/training` (`?job=`) | `POST /v1/training`, `/v1/jobs`, `/v1/jobs/{id}`, `POST /v1/jobs/{id}/cancel`, `/v1/infrastructure/workers` |
| Pareto Optimization Explorer | `/pareto` (`?session=`) | `/v1/research/results/nasbench201_cifar10_full_suite`, `/v1/searches` |
| Benchmark Comparison | `/benchmarks` | `/v1/research/results`, `/v1/research/results/{name}`, `/v1/architectures/compare`, `/v1/experiments` |
| Experiment History | `/experiments` (`?job=`) | `/v1/jobs`, `/v1/jobs/{id}`, `/v1/experiments` |
| Model Registry | `/registry` | `/v1/architectures`, `/v1/architectures/{id}`, `/v1/architectures/{id}/export`, `/v1/models`, `/v1/models/{id}/inspect` |
| System Administration | `/system` | `/health`, `/readiness`, `/v1/infrastructure/{queue,workers}`, `/v1/jobs`, `/v1/datasets`, `/v1/audit` |

`StudioShell` also polls `/health` (topbar *LIVE API DATA* / *API OFFLINE*, status bar), `/readiness`, `/v1/jobs` (nav badges) and `/v1/projects` (project selector). The previous routes `/compare`, `/results`, `/models` and `/admin` redirect (307) to `/benchmarks`, `/benchmarks`, `/registry` and `/system`.

How the spec's page names (`docs/SPEC_ACCEPTANCE.md`) map to V3 screens: Research Dashboard → Research Overview; Architecture Graph Explorer → Neural Architecture Explorer; Training Laboratory → Training and GPU Monitoring; Model Comparison and Research Results → Benchmark Comparison. Experiment History is the V3 screen for search-history inspection and error reporting.

## Explicitly unavailable

- **Generator without a checkpoint**: `POST /v1/architectures/generate` returns 503, and the Generator shows *UNAVAILABLE: trained generator*.
- **GPU telemetry** (utilisation, memory, power, temperature): the API does not collect it.
- **Latency**: the Explorer and Benchmarks screens show *NOT MEASURED*; no hardware profiler is connected.
- **Gradient and activation statistics**: no trained weights are attached to registered graphs; the Explorer's TENSOR WATCH shows analytical values only.
- **Deployments**: the API has no deployment endpoint; the Registry tab says so.
- **Job retry**: no retry endpoint exists; the button explains how to queue a new job.
- **User and API-key management, and the research-policy editor**: configuration only.
- **Audit log without a key**: shows a "needs the write API key" state.

The Explorer's analytical numbers (per-node parameters, FLOPs and activation memory) use the formulas of `archai_compiler.metrics`. They are unit-tested to sum to the API's totals (`tests/studio-v3.test.ts`), and the diagnostics console flags any mismatch.

## API client

`app/lib/api.ts` provides:

- **Base URL**: `NEXT_PUBLIC_ARCHAI_API_URL`, inlined at build time. Default `http://127.0.0.1:8000`. The production CSP `connect-src` is built from the same value.
- **Timeout**: 15 s by default; 120 s for downloads and generation.
- **Cancellation**: an `AbortController` per request. `usePoll` aborts on unmount and skips polls while the tab is hidden.
- **Errors**: typed `ApiError` kinds `network | timeout | aborted | http | invalid_response`. `request()` never throws.
- **Response validators**: in `app/lib/validators.ts`.
- **API key**: typed into the sidebar (or the key popover below 1100 px), kept in `sessionStorage` for the browser session only, and sent as `x-api-key`. No secret is compiled into the browser bundle.

## Local run

See `infrastructure/local/README.md` for the API, worker and benchmark. Then:

```bash
cd apps/web
npm ci
NEXT_PUBLIC_ARCHAI_API_URL=http://127.0.0.1:8000 npm run build   # prebuild runs the unit tests
npx next start --hostname 127.0.0.1 --port 3000
```

The browser E2E (`e2e/README.md`) covers every screen at 1920×1080, 1440×900, 1280×800, 1024×768 and 768×1024.
