# Studio browser E2E (live stack)

`studio.e2e.mjs` drives the production build (`npm run build && npx next start`) with Chrome via `playwright-core` against a running API + Redis worker + NATS-Bench archive (see `infrastructure/local/README.md`). CI runs it in the `studio-e2e` job through `scripts/ci_e2e_stack.sh`, with the committed 256-cell fixture (fixture-only, not a research result).

Live flows at 1440×900:

- create and select a research project
- command palette navigation (Ctrl+K)
- multi-objective search to completion: history, convergence chart, population board
- Pareto fronts: measured suite, candidate detail, live session
- Explorer: register via the API, graph from the registry, validation pill, `+` zoom, keyboard panel resize, operator inspector, JSON + TorchScript + local graph export
- generator: generate, validate, save to registry
- benchmark policy table and two-architecture comparison
- smoke result set
- registry architecture detail, checkpoint tensor inspection, deployments state
- synthetic training job with a measured curve, and GPU telemetry marked unavailable
- experiment filters and timeline
- system readiness, workers and audit log

Then every screen at 1920×1080, 1440×900, 1280×800, 1024×768 and 768×1024 (set `ARCHAI_E2E_VIEWPORTS` to change this) is checked for:

- active nav item
- no horizontal overflow of the document, `main` or any element
- data loads
- the Explorer graph renders
- no unnamed buttons
- browser and console panel resizing in the Explorer (wider than 800 px)

Finally, zero browser console errors are required across the whole run. A screenshot of each screen at each viewport is written to `$SCREENS`.

```bash
ARCHAI_E2E_API_KEY_FILE=/path/to/key ARCHAI_E2E_CHECKPOINT=/path/to/checkpoint.pt SCREENS=/tmp/screens npm run e2e
```

The API key is read from a file and every line the script prints is redacted, because Playwright errors can echo DOM values (including the key field).
