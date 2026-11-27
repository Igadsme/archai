# ArchAI model card

This card follows `docs/MODEL_CARD_TEMPLATE.md`. Numbers that have been measured
are labeled with their evidence type and scale. Fields waiting on a Kaggle GPU
run are wrapped as **PLACEHOLDER (not yet measured)** and must not be quoted as
results.

## Model

- Model ID: ArchAI-V1
- Kind: generator + predictor (candidate checkpoints are produced only after a Kaggle CIFAR-10 eval)
- Version: v1-draft (smoke-scale training in-repo; GPU artifacts not yet imported)
- Code revision: see the `feat/complete-archai` commit recorded in the training metadata of each checkpoint (`code_revision` in the `.pt` metadata). Do not invent a SHA here.

## Intended use

ArchAI-V1 is a research generator/predictor pair for the NATS-Bench TSS (NAS-Bench-201) cell search space on CIFAR-10. The generator models a six-edge operation sequence conditioned on a validation-accuracy quantile and a parameter-budget ceiling (`ceiling_bins`, 8-d condition). The predictor estimates validation accuracy from a cell graph. Intended users are researchers reproducing or extending this repository. This is not a production image-classifier release.

The hosted demo (when deployed) uses a 256-cell **fixture**, labeled fixture-only, and is not a substitute for the official 15,625-cell archive.

## Training evidence

### Generator (CPU smoke, measured)

- Dataset ID/version/checksum: NATS-Bench TSS CIFAR-10 table, trial 0, 2,000 training cells (subset of the official 15,625-cell table). Official archive tree SHA-256 `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`. The smoke run that selected `ceiling_bins` is recorded in `research/results/generator_budget_bins_smoke/`.
- Seed(s): 0
- Hardware: box CPU (no GPU)
- Training configuration: `ceiling_bins` condition, 300 epochs, 2,000 cells, penalty-epochs 0, tight-budget oversampling. Code at `6ca450d` / results at `f7b7e48`.
- Checkpoint SHA-256: `954cfab08e64103db499bc6171a261d29737b68915a6291bccd65acfef920cfe` (artifact lives outside git).
- Evidence type: `measured_training` for the loss; generated-cell quality is `benchmark_lookup` (not trained CIFAR-10).
- Measured quality at this smoke scale (not a production claim): raw param-budget satisfaction **0.983** vs uniform random **0.908**; mean validation accuracy **89.49** vs random **83.41**. A 40-epoch rejection-penalty ablation reached satisfaction 1.0 but dropped mean val to 74.18 and was not selected.

### Predictor (CPU smoke, measured earlier)

- Earlier smoke (commit `2fe79d1`): 1,000 cells, 30 epochs, CPU. Held-out n=100: MAE 0.0539, Spearman 0.753. Checkpoint SHA-256 `3392b86c…13d2` (outside git; full digest in TEST_REPORT). Evidence: predicted outputs scored against `benchmark_lookup` labels; test not used for selection.

### Kaggle GPU (PLACEHOLDER — not yet measured)

- **PLACEHOLDER (not yet measured):** dataset checksum of the table / archive used on Kaggle
- **PLACEHOLDER (not yet measured):** seed(s), accelerator (P100 or T4 x2), wall-clock hours
- **PLACEHOLDER (not yet measured):** generator/predictor epochs completed, training losses, checkpoint SHA-256 values from `metrics.json`
- **PLACEHOLDER (not yet measured):** any candidate CIFAR-10 validation loss or held-out test accuracy. When filled, label the protocol as this repo's `archai_training.engine` (Adam default), **not** the official NATS-Bench 200-epoch recipe.

Import from a finished Kaggle run by copying `metrics.json` plus the checksummed `generator.pt` / `predictor.pt` / `candidate_*.pt` artifacts and replacing every PLACEHOLDER line with the measured field. Do not estimate missing numbers.

## Evaluation

- Generator smoke evaluation: `benchmark_lookup` of generated cells' NATS-Bench validation accuracy and parameter count. Test accuracy from the archive was not used for model or search selection.
- Predictor smoke evaluation: held-out regression metrics against benchmark validation labels (see above).
- **PLACEHOLDER (not yet measured):** Kaggle CIFAR-10 train-and-evaluate of a few generated cells, including held-out official test accuracy if the run completed. Report validation and test separately. State that test was not used for selection.

Do not publish a Hugging Face revision that contains unresolved PLACEHOLDER fields as if they were results.

## Limitations

- Smoke-scale CPU training is not a claim about GPU or full-space quality.
- `sample()` only builds graphs from `GENERATABLE_OPS`. NAS-Bench-201 vocab checkpoints must be sampled with `sample_tokens()` and parsed as cell encodings.
- Candidate training in this repo is not the official NATS-Bench training protocol.
- The Render Hobby/Free API is planned without the `ml` extra (512 MB). Hosted generate/training that needs PyTorch is expected to be unavailable.
- The official 15,625-cell archive is not served from the free host; the 256-cell fixture is for demo and CI only.
- This card will stay draft / private on the Hub until Imani provides a fine-grained write token and reviews the measured GPU fields.
