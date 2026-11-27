# Security

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Use GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on `Igadsme/archai`, or contact the maintainer directly.
Include the affected commit, a reproduction, and the impact. Expect an acknowledgement within a few days.

## Threat model

- **Architecture specifications are untrusted data.** The compiler uses an allowlisted operator
  registry and never imports or executes user code.
- **Checkpoints are untrusted files.** They are loaded with `torch.load(..., weights_only=True)`,
  registered with a SHA-256 manifest, and refused (HTTP 409) when the file no longer matches.
- **Filesystem paths from API clients** (corpora, checkpoints, archives) must sit under
  `ARCHAI_ALLOWED_PATHS`; anything else is rejected before a job is queued and again in the worker.
- **Datasets and benchmark archives** are checksum-gated; acquisition accepts only `https`, `http`
  and `file` URLs and promotes a download only after its SHA-256 matches.
- **Expensive work** (search, training, generation) requires the write key whenever one is configured,
  is bounded by request validation, rate-limited per client, cancellable, and audit-logged.

## Deployment controls

| Control | How |
| --- | --- |
| Production switch | `ARCHAI_ENV=production` refuses to boot without a key, with `*`/non-https/localhost CORS origins, without `DATABASE_URL`/`ARCHAI_REDIS_URL`, or with `ARCHAI_DB_AUTO_CREATE=1`; it also disables `/docs` unless `ARCHAI_DOCS_ENABLED=1` and sends HSTS. |
| Authentication | User accounts own managed API keys (`ak_<prefix>_<secret>`, 256-bit) with explicit `read` / `write` / `admin` scopes, optional expiry, rotation and revocation. Only the SHA-256 of each key is stored; the secret is returned once. The bootstrap key from `ARCHAI_API_KEY` / `ARCHAI_API_KEY_SHA256` is an admin credential with no user, so access to key management can always be recovered. Keys are sent as `x-api-key` or `Authorization: Bearer`. Auth is on when a bootstrap key is set or any managed key is active. `ARCHAI_PROTECT_READS=1` also guards every read except `/health`, `/readiness` and `/v1/auth/whoami`. |
| Rate limits | Per client IP and per read/write class, shared through Redis. Run uvicorn with `--proxy-headers` and set `FORWARDED_ALLOW_IPS` to the proxy so limits see real client IPs. |
| Request limits | `ARCHAI_MAX_REQUEST_BYTES` (default 1 MiB), enforced even without `Content-Length`; malformed lengths get 400. |
| Headers | API: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, `default-src 'none'` CSP, HSTS in production. Studio: CSP restricting `connect-src` to the API origin, `frame-ancestors 'none'`, `nosniff`. |
| Audit | Every state-changing request (including 401/413/429 rejections) is logged as JSON with a request ID and a 12-hex credential fingerprint plus the managed key id (or `bootstrap`), never the key. `GET /v1/audit` (admin scope when auth is on) and the Studio admin page read it. |
| Containers | Non-root users (API `10001`, Studio `node`), CPU-only torch, health checks, Redis AOF persistence for the job queue, internal-only Postgres/Redis in Compose. |
| Supply chain | CI runs `pip-audit`, `npm audit --audit-level=high`, ruff's flake8-bandit rules, and builds + smoke-tests both images; Dependabot watches pip, npm, Actions and base images. |

## Known limits

- Accounts authenticate with API keys only (no passwords, SSO or sessions). Key management is admin-only.
- Without a bootstrap key, the first managed key must be admin-scoped, and the last active admin key cannot be revoked or its owner disabled.
- On Render the proxy's addresses are not fixed, so `X-Forwarded-For` is trusted from any hop and
  per-client rate limits are best-effort there.
- The Studio stores the key in `sessionStorage` for the browser session; it is never baked into the bundle.
- Next.js inline bootstrap scripts require `script-src 'unsafe-inline'` in the Studio CSP.
