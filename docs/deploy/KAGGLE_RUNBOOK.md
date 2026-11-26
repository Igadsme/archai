# Kaggle runbook (free GPU, Imani runs this)

The box does not start a Kaggle session and does not use paid Colab Pro hours.
Imani runs `notebooks/archai_v1_kaggle_train.ipynb` on a free Kaggle GPU and
downloads the checksummed artifacts plus `metrics.json` for us to import.

Read `FREE_TIER_PLAN.md` first. Official Kaggle limits (verified 2026-11-26):

- Weekly GPU quota: **30 hours** (sometimes higher). Check remaining time under
  Kaggle account settings before you start.
- GPU session length: **12 hours**. The job is planned for about **9 hours**
  with checkpoints every 15 minutes and `--resume` if you have to rerun.
- Interactive idle: docs disagree (20 vs 60 minutes). Do not leave an
  interactive session idle; use **Save & Run All** (or Save Version → Save &
  Run All) so the job runs to completion without you watching it.
- `/kaggle/working` keeps 20 GB. Stop the session when you are done so idle
  time is not charged against the quota.
- Do **not** link Colab Pro for extra GPU hours (paid).

## 1. One-time: get NATS-Bench onto Kaggle

The official `NATS-tss-v1_0-3ffb9-simple` archive is ~1.15 GB. The notebook
will not silently skip checksums. Pick **one** of the two paths.

### Path A — official Google Drive download inside the notebook (preferred)

The official URI and SHA-256 are in `datasets/manifests/natsbench201.json`:

- Google Drive file id: `17_saCsj_krKjlCBLOJEpNtzPXArMCqxU`
- Tar SHA-256: `580fd8f3425fed9f495640b0f12ccb7744f89dec7aff263bd75aed37ab0b8bb6`
- Extracted directory tree SHA-256: `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`

The notebook cell installs `gdown`, downloads the tar to `/kaggle/working`,
verifies the tar digest, extracts it, and verifies the tree digest. If either
checksum fails, stop; do not train. This uses the official source and does not
need a Kaggle dataset upload.

Google Drive can throttle or prompt. If `gdown` fails, use Path B.

### Path B — Imani uploads a private Kaggle dataset

1. On a machine that already has the verified archive (the box copy lives
   outside git; the tar SHA-256 must be `580fd8f3…8bb6` or the extracted tree
   SHA-256 must be `183b6ad8…4ba3`), pack the extracted directory or the tar.
2. Sign in at [https://www.kaggle.com](https://www.kaggle.com) → Datasets →
   New Dataset. Name it e.g. `nats-bench-tss-simple`. Visibility: **Private**.
   Upload the tar or the extracted folder. Create the dataset. Do not make it
   public; this repo is not a distribution point for the 1.15 GB archive.
3. In the notebook, click **Add Input** (or Add Data) → Datasets → your
   private dataset. Kaggle mounts it under `/kaggle/input/<slug>/`.
4. Set `ARCHIVE` or `TAR` in the notebook config cell to that path. The
   prepare cell still verifies the official SHA-256 before building the table.

A pre-built `cifar10.jsonl` table (15,625 rows, from
`scripts/benchmark_table.py`) can also be uploaded as a private dataset. If you
attach it, set `TABLE` to that JSONL and skip archive extraction / tabulation.

## 2. Create the notebook on Kaggle

1. Sign in at [https://www.kaggle.com](https://www.kaggle.com). Confirm GPU
   quota remains (Settings → or the accelerator picker). You need ~9 hours
   plus a margin in the weekly 30-hour quota, and a 12-hour session window.
2. Code → New Notebook. In Settings / Notebook options:
   - Accelerator: **GPU** (P100 or T4 x2, whichever Kaggle offers; both are
     documented as free). If the GPU is queued, wait or try later. Do not
     switch to a paid add-on.
   - Internet: **On** (to clone this repo, and for Path A / CIFAR-10 download).
   - Persistence: default is fine; outputs land in `/kaggle/working`.
3. File → Import Notebook, or copy the cells from
   `notebooks/archai_v1_kaggle_train.ipynb` in this repo (File → Upload if you
   prefer to upload the `.ipynb` from a clone). The committed notebook is the
   source of truth; do not retype hyperparameters from memory.
4. If you used Path B, click Add Input and attach the private dataset now.
5. In the first **config** cell, set:
   - `REPO_URL` = `https://github.com/Igadsme/archai.git`
   - `REPO_REF` = `feat/complete-archai` (or the commit Imani wants)
   - `ARCHIVE` / `TAR` / `TABLE` according to Path A or B
   - `RESUME` = `False` on a first run, `True` if `/kaggle/working/archai_v1`
     already has checkpoints from a previous Save Version
   - Leave `SMOKE = False` for the real ~9 h run. `SMOKE = True` is only for
     a minutes-long dry check (fixture, no official archive, no CIFAR-10).
6. Click **Save Version** → Version type **Save & Run All** → Accelerator GPU
   → Save. This is the 12-hour batch run. You can close the browser. Do not
   use a long interactive session if you might go idle.
7. When the version finishes (or if it dies at the 12-hour cap), open the
   output. You want:
   - `/kaggle/working/archai_v1/metrics.json` (includes SHA-256 fields and
     `wall_clock_seconds`)
   - `generator.pt`, `predictor.pt`, `generator_state.json`,
     `predictor_state.json`
   - `candidate_*.pt` for any CIFAR-10 evals that completed, plus
     `cifar10_eval.json`
8. Download those files (Output → Download). The next session can import
   them, fill the PLACEHOLDER fields in `MODEL_CARD.md`, and only then talk
   about a Hugging Face publish.
9. If the run stopped early (`stopped_for_time_budget` or a cancelled /
   failed version), start a new Save & Run All with `RESUME = True` and the
   previous output available (Kaggle can keep `/kaggle/working` across
   versions when you rerun the same notebook; if not, upload the checkpoint
   folder as a dataset and point `OUTPUT` at a copy under `/kaggle/working`).

## 3. What the job does

1. Installs this repo with the `ml` and `benchmark` extras.
2. Acquires and checksum-verifies NATS-Bench (Path A or B) unless `TABLE` is
   already set, then builds `cifar10.jsonl` with `scripts/benchmark_table.py`
   if needed (also checksum-verified).
3. Runs `scripts/kaggle_train_archai_v1.py` for up to 9 hours:
   - trains the ArchAI-V1 generator on all 15,625 cells (`ceiling_bins`, 2000
     epochs planned) with checkpoints every 15 minutes
   - trains the predictor on the same table (80 epochs planned)
   - trains and evaluates a few generated cells on real CIFAR-10 (this repo's
     engine, not the official 200-epoch NATS-Bench recipe) and writes
     held-out official test accuracy when a candidate finishes
4. Writes `metrics.json` with checksums. Wall-clock time in that file is
   measured; the "9 hours" figure in this runbook is only a budget.

A CPU smoke of the same script (`--smoke`) is what we run on the box and in
the `python-torch` CI job. That path is labeled `cpu_smoke` and must not be
reported as a GPU result.

## 4. After the run

Send or store, without putting secrets in the repo:

- `metrics.json`
- the SHA-256 of each `.pt` file (already inside `metrics.json` if the script
  finished the corresponding step)
- the checkpoint files themselves, outside git (same convention as the smoke
  checkpoints)

We will import those numbers into `MODEL_CARD.md` only as measured fields.
