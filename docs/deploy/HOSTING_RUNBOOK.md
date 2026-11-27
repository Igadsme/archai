# Hosting runbook (free tier only)

Imani does these steps. This repository does not create accounts, does not start
trials, and does not add a payment card. Read `FREE_TIER_PLAN.md` first. Official
limits were verified on 2026-11-26 and can change.

**Do not add a payment method** to Vercel, Render, Neon, or Upstash. Upstash will
convert every free database to a paid plan if a card is added. Render will bill
bandwidth/build overages if a card is on file.

The frontend is Vercel Hobby. The API is one Render **free web service** with the
worker embedded in the same process. Postgres is Neon Free. Redis is Upstash Free.
The hosted benchmark is the committed 256-cell fixture, not the official archive.

## 0. What you will need before clicking Deploy

- This GitHub repo (`Igadsme/archai`) and the `feat/complete-archai` branch (or a
  later revision Imani chooses).
- A password manager, for three secrets you will generate: a production API key,
  plus the Neon and Upstash URIs the dashboards will show.
- About 20–30 minutes, mostly sign-up and pasting env vars.

## 1. Neon Free (Postgres)

1. Open [https://neon.tech](https://neon.tech) and click Sign up. Use GitHub if you
   want. Stay on the **Free** plan. Do not choose Launch or Scale. Do not add a card.
2. Create a project (name it `archai`). Region: pick one close to `iad` (Vercel
   is set to `iad1` in `apps/web/vercel.json`); US East is a reasonable default.
3. Wait until the project shows a ready database.
4. Open Connect / Connection details. Copy the **pooled** connection string
   (host contains `-pooler`). This is `DATABASE_URL`. It looks like
   `postgresql://…@….neon.tech/…?sslmode=require`. Store it in your password
   manager. Do not commit it.
5. Leave the project as-is. Free-plan compute will scale to zero after 5 minutes
   idle; the API will wait on the first query after a nap. That is expected.

## 2. Upstash Redis (Free)

1. Open [https://upstash.com](https://upstash.com) and sign up (GitHub is fine).
2. **Do not add a payment method.** Upstash docs state that adding the first
   payment method moves every free resource to a paid plan, and an account with
   a payment method cannot have free databases.
3. Create a Redis database: type Redis, region close to Neon, **Free** evictions /
   the Free plan. One database only on Free (250 MB, 500K commands/month).
4. Copy the TLS URL (`rediss://default:…@….upstash.io:6379`). This is
   `ARCHAI_REDIS_URL`. Store it. Do not commit it.

## 3. Generate a production API key (on your machine)

In a local terminal, **do not** paste the plaintext into the git repo:

```bash
python -c "import secrets,hashlib; k=secrets.token_urlsafe(32); print('ARCHAI_API_KEY_SHA256='+hashlib.sha256(k.encode()).hexdigest()); print('plaintext (store in a password manager, not on Render):'); print(k)"
```

Keep the plaintext for the Studio UI and for any `x-api-key` / Bearer clients.
Paste only `ARCHAI_API_KEY_SHA256` into Render.

## 4. Render free web service (API + embedded worker)

1. Open [https://render.com](https://render.com) and sign up. Use GitHub. Stay on
   the Hobby workspace with **Free** compute. Do not add a card. Do not click
   Upgrade. Do not create a Background Worker, Cron Job, Private Service, or
   Render Postgres/Key Value instance.
2. New + Blueprint, or New + Web Service. Connect the `Igadsme/archai` GitHub
   repo. If you use the Blueprint, Render will read `render.yaml` at the repo
   root. Branch: `feat/complete-archai` (or the branch Imani chooses).
3. Confirm the service is a **Web** service, plan **Free**, build command
   `pip install --upgrade pip && pip install '.[platform]'` (no `ml` extra),
   pre-deploy `alembic upgrade head`, start
   `uvicorn archai_api.main:app --host 0.0.0.0 --port $PORT`.
4. Auto-deploy is off in `render.yaml` so a red CI push does not go live. Imani
   clicks Manual Deploy when she wants a release.
5. Fill the unsynced env vars from `render.yaml` / `ENV.md`:

   - `DATABASE_URL` — Neon pooled URI
   - `ARCHAI_REDIS_URL` — Upstash `rediss://` URI
   - `ARCHAI_API_KEY_SHA256` — the hash from step 3
   - `ARCHAI_CORS_ORIGINS` — leave a placeholder for now, e.g.
     `https://localhost.invalid`, then replace it with the Vercel origin after
     step 5 (a rebuild of the API is needed after the change).

   The fixture path, fixture SHA-256, `ARCHAI_EMBED_WORKER=1`,
   `ARCHAI_REQUIRE_API_KEY=1`, and `ARCHAI_NATS_BENCH_INDICES=fixture` are
   already set in `render.yaml`.
6. Deploy. The first boot may take several minutes (build + pip + migrate).
   The service will exist at `https://<name>.onrender.com`. Open `/health`
   (should be 200) and `/readiness` (should become ready once Neon wakes).
7. Confirm a write without a key is rejected: `POST /v1/projects` with no
   `x-api-key` must return **401**. The process must not boot if the key hash
   is missing (`ARCHAI_REQUIRE_API_KEY=1`).
8. Expect a ~1 minute cold start after 15 minutes idle. That is the Free plan.
   In-flight jobs die on spin-down; Redis can requeue after the lease expires
   when the service is up again.

If deploy fails on `alembic upgrade head`, check `DATABASE_URL` (pooled host,
`sslmode=require`) and that you stayed on Neon Free rather than an empty URL.

## 5. Vercel Hobby (Studio)

1. Open [https://vercel.com](https://vercel.com) and sign up with GitHub. Stay
   on **Hobby**. Do **not** start a Pro trial (that flow asks for a card).
2. Add New Project → import `Igadsme/archai`.
3. Set **Root Directory** to `apps/web`. Framework: Next.js. Install `npm ci`,
   build `npm run build` (also in `apps/web/vercel.json`).
4. Environment variable (Production and Preview):

   - `NEXT_PUBLIC_ARCHAI_API_URL` = `https://<render-service>.onrender.com`
     (no trailing slash). This is inlined at **build** time; change it only if
     you are willing to redeploy the frontend.
5. Deploy. Copy the production origin, e.g. `https://archai-studio.vercel.app`
   (or the `.vercel.app` URL Vercel assigns).
6. Return to Render. Set `ARCHAI_CORS_ORIGINS` to that exact origin (scheme +
   host, no path, no trailing slash). Manual Deploy the API again so CORS takes
   effect (`ARCHAI_CORS_ORIGINS` is read at process start).
7. Open the Studio. Paste the **plaintext** API key into the Studio API-key
   field. Create a project. Search jobs run against the 256-cell fixture and
   are labeled fixture-only — not a full-benchmark result.
8. If the first Studio request after idle is slow, wait for Render (~1 min) and
   Neon (~seconds) to wake. Do not upgrade to remove cold starts.

## 6. What not to do

- Do not add cards, Pro/Launch/Scale upgrades, Render workers, Render Postgres,
  Render cron, Hugging Face PRO, or Kaggle Colab Pro hours.
- Do not upload the official NATS-Bench archive to Render or Vercel.
- Do not set `ARCHAI_CORS_ORIGINS` to `*` or leave production without
  `ARCHAI_REQUIRE_API_KEY=1`.
- Do not turn on Render auto-deploy until Imani wants every green push live.

## 7. After a deploy, smoke-check

```bash
# health (no key)
curl -sS https://<api>.onrender.com/health
# writes without a key must be 401
curl -sS -o /tmp/archai-no-key.json -w '%{http_code}\n' \
  -X POST https://<api>.onrender.com/v1/projects \
  -H 'content-type: application/json' -d '{"name":"probe"}'
# writes with the plaintext key should succeed
curl -sS -X POST https://<api>.onrender.com/v1/projects \
  -H 'content-type: application/json' -H "x-api-key: $ARCHAI_API_KEY" \
  -d '{"name":"hosted-demo"}'
```

Replace hostnames and do not commit the curl history if it contains the key.
