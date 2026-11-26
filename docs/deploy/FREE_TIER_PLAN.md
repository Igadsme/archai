# Free-tier plan (verified 2026-11-26)

Imani chose a no-cost path on 2026-11-26, 12:46 AM America/New_York: Kaggle free GPU, Hugging Face free private model hosting, and Vercel + Render + Neon + Upstash free hosting. This page records what the **official** pricing/docs said on that date, with source links. Limits change; re-check the links before a long run or a signup.

**Standing rule:** do not add a payment card, do not start a paid trial, and do not upgrade a service. Several of these vendors will bill overages *only if a card is on file*, or will convert free resources to paid when a card is added.

| Service | Officially free for this plan? | Card required to stay free? | Surprises |
| --- | --- | --- | --- |
| Kaggle Notebooks GPU | Yes (weekly quota) | No | 12-hour session cap; weekly quota is 30 hours (sometimes higher). Colab Pro extra hours are a **paid** add-on — do not use it. |
| Hugging Face Hub (private model repo) | Yes, 100 GB private storage on a free account | No, if you stay in the free 100 GB | Storage above the free private quota is billed on paid plans; stay under 100 GB and do not buy PRO or storage add-ons. |
| Vercel Hobby (Studio frontend) | Yes, $0 included usage | No (do not start a Pro trial; that form asks for a card) | Exceeding Hobby usage **pauses** the feature; you cannot buy more usage on Hobby. Read the [Terms](https://vercel.com/legal/terms) before any commercial use. |
| Render free **web** service (API) | Yes, with hard limits | **Do not add a card.** If a card is on file, extra bandwidth or build minutes are billed; without a card, services are suspended instead. | **No free Background Workers, Cron Jobs, or Private Services.** Free web services spin down after 15 minutes idle (~1 minute cold start), 750 instance hours/month, 512 MB RAM, 5 GB Hobby outbound bandwidth/month, ephemeral disk. |
| Render free Postgres / Key Value | Exist, but **not used** here | Do not add a card | Free Postgres **expires after 30 days** (then a paid upgrade is required to keep the data). Free Key Value is in-memory only and loses data on restart. We use Neon and Upstash instead. |
| Neon Free (Postgres) | Yes, $0/month | No card required for the Free plan | Compute scales to zero after 5 minutes and **cannot** be disabled on Free. Hitting CU-hour or transfer caps suspends compute until the next month; Neon does not bill Free-plan overages. |
| Upstash Redis Free | Yes, one free database, no card | **Do not add a card.** Adding the first payment method **moves every free database to a paid plan**. | 250 MB, 500K commands/month, 10 GB bandwidth, 1 database. |

## Kaggle

Sources (fetched 2026-11-26):

- [Efficient GPU Usage Tips](https://www.kaggle.com/docs/efficient-gpu-usage)
- [Notebooks / Technical Specifications](https://www.kaggle.com/docs/notebooks)

Documented limits:

- Weekly GPU quota: **30 hours**, "or sometimes higher depending on demand and resources." The quota resets weekly. Remaining time is in account settings.
- Hardware (at time of writing, per the Notebooks doc): NVIDIA Tesla **P100** (4 CPU, 29 GB RAM) or **T4 x2** (4 CPU, 29 GB RAM). Free GPUs can queue when busy.
- Session length: **12 hours** execution for CPU and GPU notebook sessions (**9 hours** for TPU). "Save & Run All" must finish within that same cap. This repo plans a **~9 hour** GPU job so it fits inside a 12-hour GPU session and the 30-hour weekly quota, with checkpoints and resume if the session dies.
- Disk: 20 GB auto-saved under `/kaggle/working`; extra scratch is not kept after the session.
- Idle: the GPU-usage page says interactive sessions stay up until a **60-minute** idle timeout; the Notebooks editor page says **20 minutes** of idle time while editing. Stop the session when you leave the window so idle time is not charged against the quota.
- Do **not** link Colab Pro/Pro+ for extra GPU hours. That promotion requires a paid Colab subscription.

## Hugging Face Hub

Sources (fetched 2026-11-26):

- [Storage limits](https://huggingface.co/docs/hub/en/storage-limits)
- [Pricing](https://huggingface.co/pricing)
- [Billing](https://huggingface.co/docs/hub/billing)

Documented limits:

- Free user or org: **100 GB private** storage, public storage on a best-effort basis.
- PRO and storage add-ons are paid ($9/month PRO, public storage add-on from $12/TB/month, private overage $18/TB/month on paid plans). Do not upgrade.
- Private-first publish is allowed on the free tier. Keep the ArchAI-V1 repo **private** until Imani decides otherwise.
- A fine-grained write token is required only when actually publishing. This repo's `scripts/publish_hf.py` defaults to `--dry-run` and will not call the Hub API in that mode, even if `HF_TOKEN` is set.

## Vercel Hobby (frontend)

Sources (fetched 2026-11-26):

- [Hobby plan](https://vercel.com/docs/plans/hobby)
- [Pricing](https://vercel.com/pricing)
- [Limits](https://vercel.com/docs/limits)
- [Terms of Service](https://vercel.com/legal/terms)

Documented included usage (Hobby is $0/month; unused quota does not convert to a bill):

- 1,000,000 CDN requests, 100 GB fast data transfer, 10 GB fast origin transfer
- 1,000,000 function invocations, 4 CPU-hours, 360 GB-hours provisioned memory
- 200 projects, 100 deployments/day, 45 minutes build, 5-minute function duration
- If you exceed a Hobby limit, the feature **pauses** until the next 30-day window. Hobby cannot buy extra usage.

Do **not** click Upgrade / start a Pro trial (the upgrade flow asks for a card). Read Vercel's terms before any commercial use of the Hobby plan.

## Render (API process only)

Sources (fetched 2026-11-26):

- [Deploy for Free](https://render.com/docs/free)
- [Your first deploy](https://render.com/docs/your-first-deploy) ("Note that free instances are not available for these service types" — Private Services, Background Workers, Cron Jobs, Workflows)
- [Compute plans](https://render.com/docs/compute-plans) (Background worker plans start at `0.5c-512mb`, paid)
- [Pricing](https://render.com/pricing)
- [Outbound bandwidth](https://render.com/docs/outbound-bandwidth)

### Free web services (we use one)

- $0, 0.1 CPU, 512 MB RAM (`free` compute plan).
- Spins down after **15 minutes** without inbound traffic; spin-up is about **one minute**.
- **750 Free instance hours** per workspace per calendar month (idle spun-down time does not count). Exhausting them suspends free web services until next month.
- Hobby workspace outbound bandwidth included: **5 GB/month**. Usage above that is billed at $0.15/GB **if a payment method is linked**; otherwise Render **spins down / suspends** services until next month. Build-pipeline overage is the same: billed if a card is present, otherwise new builds are disabled.
- Ephemeral filesystem; no persistent disk on Free. No SSH, no scaling above one instance.
- Render may restart a free web service at any time.

### Free background workers: **do not exist**

Official docs: only Static Site, Web Service, Postgres, and Key Value support Free instances. Background workers, cron jobs, and private services have **no free compute plan**. The cheapest worker is a paid 0.5 CPU / 512 MB instance.

**Plan:** run the durable worker **inside the API web process** (`ARCHAI_EMBED_WORKER=1`). Search and training jobs are handled on the same 512 MB free web service. This is a compromise: a spin-down still drops in-flight jobs (Redis can requeue after the lease expires when the process comes back).

Do **not** create a Render Background Worker, Cron Job, or paid compute plan.

### Render Postgres / Key Value (not used)

- Free Postgres: 1 GB, **one per workspace**, **expires 30 days after creation**; after a 14-day grace period the database is deleted unless upgraded to a paid plan.
- Free Key Value: one per workspace, not persisted to disk, data lost on restart.

We use **Neon** and **Upstash** instead so a 30-day Render Postgres expiry cannot force a paid upgrade.

## Neon Free (Postgres)

Sources (fetched 2026-11-26):

- [Plans](https://neon.com/docs/introduction/plans) (page dated 2026-11-24)
- [Free plan limits FAQ](https://neon.com/faqs/free-plan-limits-and-quotas) (updated 2026-11-03)

Documented limits:

- $0/month. Neon documents the Free plan as usable without paying; do not switch to Launch/Scale (those are pay-for-what-you-use).
- 100 projects, 10 branches/project, **1 GB Postgres storage/project** (20 GB account cap), **5 GB** public transfer/project/month, **100 CU-hours** compute/project/month.
- Autoscaling up to 2 CU; **scale to zero after 5 minutes, cannot be disabled** on Free. The API must tolerate a cold start on the first query after idle.
- Exhausting CU-hours or transfer **suspends compute** until the next month; Neon says it does **not** bill overages on the Free plan.
- Instant restore history: 6 hours, capped at 1 GB of change history.

## Upstash Redis Free

Sources (fetched 2026-11-26):

- [Pricing & Billing](https://upstash.com/docs/redis/overall/billing)
- [Redis pricing](https://upstash.com/pricing/redis)

Documented limits:

- $0/month, **no credit card required**, one free database: **250 MB** data, **500,000 commands/month**, **10 GB** bandwidth, 10,000 commands/sec, 10 MB max request, 100 MB max record.
- **Critical:** "Adding your first payment method moves every free resource on the account to its paid plan… An account with a payment method cannot have free databases." Do not add a card to Upstash, even "just in case."

The job queue and rate limiter will count against the 500K command/month cap. A spun-down API that restarts often should still stay well under that for a private demo; watch the Upstash dashboard if the Studio is left polling.

## Hosted dataset policy

The official NATS-Bench TSS `*-simple` archive is ~1.15 GB (see `datasets/manifests/natsbench201.json`). The [NATS-Bench repository license](https://github.com/D-X-Y/NATS-Bench/blob/main/LICENSE.md) is MIT, and the authors distribute the archive from Google Drive. Even so, a Render free web service **cannot** hold or use that archive: there is no persistent disk, the slug plus 1 GB archive will not fit comfortably in 512 MB RAM, and a public demo should not be the distribution point for the full benchmark.

**The hosted API uses the committed 256-cell fixture** at `datasets/fixtures/natsbench-tss-cifar10-256` (labeled fixture-only, not a research result). Imani keeps the official archive on the box and/or as a **private** Kaggle dataset for the GPU training run.

## What this plan will not do

- No paid Render worker, no Render free Postgres (30-day fuse), no Upstash/Render/Vercel/Neon/HF paid upgrade, no Kaggle Colab Pro hours, no Vercel Pro trial, no card on file.
- No Hugging Face publish until Imani provides a token and GPU artifacts exist (the script can be dry-run now).
- PyTorch likely will not fit in Render's 512 MB free web instance. The hosted API is installed **without** the `ml` extra; `/v1/architectures/generate` and training jobs that need torch return an error. Search, projects, and registry work against the fixture.
