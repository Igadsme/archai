# Generator checkpoints

`POST /v1/architectures/generate` samples from the checkpoint named by `ARCHAI_GENERATOR_CHECKPOINT`. With no checkpoint, or one that cannot be loaded, it answers `503` and the Studio Generator screen says so. It never simulates candidates.

## Train one locally (CPU, under a minute)

```bash
python scripts/train_generator_local.py \
  --checkpoint artifacts/generator/local.pt \
  --report artifacts/generator/local-report.json
export ARCHAI_GENERATOR_CHECKPOINT="$PWD/artifacts/generator/local.pt"
```

`ARCHAI_ALLOWED_PATHS` must include the checkpoint's directory when it is set (local mode allows `/tmp` by default). The docker compose stack trains this checkpoint into its artifact volume on first boot; see `docs/deploy/LOCAL.md`.

### What it learns, and what it does not

- **Corpus:** 4,096 random chains of 8 operations from the vocabulary the API builds graphs from (`conv3x3`, `conv1x1`, `avg_pool3x3`, `skip`), at 3×32×32 input. Each chain is labelled with its exact analytical FLOP count. The corpus is synthetic; no dataset is downloaded.
- **Condition:** the FLOPs budget as a fraction of the most expensive chain (all `conv3x3`) at the request's input spec, in 6 bins (`analytical_flops_budget_v1`, declared in the checkpoint metadata). 15% of training rows use the all-zero code, so a request with no budget samples the corpus distribution.
- **API use:** when the checkpoint declares this encoding and a request has `constraints.max_flops` but no explicit `condition`, the API picks the largest bin under the budget. The response reports `condition` and `condition_source`. Constraint filtering still runs on every candidate.
- **Not learned:** accuracy. These checkpoints know nothing about how well a candidate trains. Their metadata label says so, and the Studio shows that label next to the candidates.

The report records the loss curve, validity, uniqueness and diversity, and *budget adherence*: for each budget, the share of sampled chains at or under it, conditioned versus unconditioned. Default run on a 4-core CPU (about 8 s of training):

| FLOPs budget | Within budget, conditioned | Within budget, unconditioned |
| --- | --- | --- |
| 1/3 | 97% | 62% |
| 1/2 | 96% | 81% |
| 2/3 | 96% | 89% |
| 5/6 | 99% | 95% |

`--corpus-size`, `--epochs`, `--hidden-dim` and `--seed` change the run; the defaults are sized for a laptop.

## Train a bigger one

An accuracy-aware generator needs measured accuracies, which come from NAS-Bench-201 / NATS-Bench (about 1.15 GB) and a GPU. That pipeline is `scripts/train_generator_nb201.py`, run on a free Kaggle GPU through `notebooks/archai_v1_kaggle_train.ipynb` (`scripts/kaggle_train_archai_v1.py`). `docs/deploy/KAGGLE_RUNBOOK.md` covers quota, dataset checksums and artifact import. Those checkpoints use the NAS-Bench-201 cell vocabulary (`nor_conv_3x3`, `skip_connect`, …), and `sample()` builds chain graphs only from `GENERATABLE_OPS`, so the API cannot serve them yet. They are used by the benchmark search policies. Serving cell-vocabulary checkpoints through `/generate` would need a cell-to-graph decoder.

For a larger chain-vocabulary model on a local GPU or a bigger CPU, raise `--corpus-size` (for example 65,536), `--epochs` and `--hidden-dim`. `fit_sequences` trains full-batch on CPU, so corpus size is limited by memory, roughly linearly.
