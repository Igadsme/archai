# Studio browser E2E (live stack, not CI)

`studio.e2e.mjs` drives the production build (`npm run build && npx next start`) with the system Chrome via
`playwright-core` against a running API + Redis worker + NATS-Bench archive (see `infrastructure/local/README.md`).

Checks: all ten spec pages at 1280×900 (nav state, data loads, no unnamed buttons) and 390×844 (no horizontal
overflow, menu toggle); real flows — multi-objective search to completion, Pareto fronts (measured suite + live
session), graph register/draw/JSON + TorchScript export, generator → registry, architecture comparison, checkpoint
inspection, synthetic training job, research results, system administration; and zero browser console errors.

```bash
ARCHAI_E2E_API_KEY_FILE=/path/to/key ARCHAI_E2E_CHECKPOINT=/path/to/checkpoint.pt SCREENS=/tmp/screens npm run e2e
```

The API key is read from a file and every line the script prints is redacted, because Playwright errors can echo
DOM values (including the key field).
