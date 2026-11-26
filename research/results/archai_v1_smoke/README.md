# ArchAI-V1 smoke-scale training on real NATS-Bench TSS data

**Scale: CPU smoke.** These are small, single-seed runs. They show that the models train on
real benchmark data, save, reload and produce useful signal. They are not tuned or
production models, and they say nothing about larger scales.

Archive: official `NATS-tss-v1_0-3ffb9-simple` (tree SHA-256 `183b6ad8…4ba3`; see
`datasets/manifests/natsbench201.json`). Checkpoints live outside git in `/workspace/archai-data/checkpoints/`.

| Model | Checkpoint SHA-256 | Code revision | Data | Command |
| --- | --- | --- | --- | --- |
| Predictor (graph encoder, Gaussian head) | `3392b86c628be7d4b627ac6ff23a0367efe0c2c80b12854e403f9c2906c613d2` | 2fe79d1 | 1,000 random cells (`random.Random(0).sample(range(15625), 1000)`), cifar10-valid validation accuracy, archive trial for seed 0; 800/100/100 split by architecture hash | `scripts/train_predictor.py --seed 0 --epochs 30` |
| Generator (conditional autoregressive GRU, NB201 vocabulary) | `0ad684a2ae3cd7d9db911da104ca78b17cd8fce30a52a378b29726d379ad784e` | b6fb591 | 2,000 random training cells from the full benchmark table (`scripts/benchmark_table.py`), conditioned on (validation-accuracy quantile, params/1.6M) | `scripts/train_generator_nb201.py` (defaults: 300 epochs, seed 0) |

`checkpoint_verification.json` (`scripts/verify_checkpoints.py`) confirms both SHA-256s match the
reports, that the reloaded predictor reproduces its held-out test metrics, and that the reloaded
generator reproduces its samples.

## Predictor (held-out cells; targets are accuracy fractions; evidence: measured on benchmark labels)

| Split | n | MAE | RMSE | Spearman | Kendall | 95% interval coverage | Calibration error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| validation | 100 | 0.0401 | 0.0487 | 0.716 | 0.544 | 1.00 | 0.132 |
| test | 100 | 0.0539 | 0.0922 | 0.753 | 0.558 | 0.98 | 0.115 |

## Generator (1,000 samples per row; quality = benchmark-lookup validation accuracy of the unique generated cells)

| Sampling | Valid (in space / connected) | Unique | Novel vs. train | Mean pairwise Hamming | ≤0.8M params | Mean val. acc. | Best val. acc. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Trained, condition = high accuracy, ≤0.8M params | 1.000 / 0.999 | 0.714 | 0.881 | 4.37 | 0.690 | 89.18 | 91.47 |
| Trained, condition = low accuracy | 1.000 / 0.975 | 0.531 | 0.853 | 4.09 | 0.576 | 83.95 | 91.08 |
| Untrained generator (baseline) | 1.000 / 0.982 | 0.973 | 0.865 | 4.80 | 0.850 | 84.42 | 91.55 |
| Uniform random cells (baseline) | 1.000 / 0.973 | 0.964 | 0.872 | 4.81 | 0.924 | 83.24 | 91.49 |

What this shows (single seed, so no confidence interval): the accuracy condition moves the mean
quality of generated cells (89.18 high vs. 83.95 low, against 83.24 for random cells). The
parameter-budget condition does **not** work at this scale: only 69% of high-accuracy samples meet
the 0.8M limit, compared with 92% of random cells, because accurate cells tend to be larger.
Training also lowers uniqueness and diversity. Training loss went from 1.613 to 1.278.
