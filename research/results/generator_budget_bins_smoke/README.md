# CPU-smoke generator with binned budget-ceiling conditioning

Measured on 2026-11-25, 11:59 PM America/New_York. Scale: 2000 training cells, 300 MLE epochs, seed 0, NATS-Bench TSS CIFAR-10 trial 0 (evidence: `benchmark_lookup` for generated-cell quality; `measured_training` for the loss). Evaluation condition: accuracy quantile 0.95 and a 0.8M-parameter ceiling, encoded as an 8-d vector (`acc_q`, `ceiling/1.6`, 6-bin one-hot). Samples: 1000. This is a CPU smoke-scale run, not a production-quality claim.

The selected method is `ceiling_bins` with tight-budget oversampling and **no** rejection-aware penalty (`--penalty-epochs 0`). A 40-epoch penalty ablation is reported below and was not selected.

## Selected run (`penalty-epochs 0`)

Code revision `6ca450d` (training was rerun on a clean tree of that commit). Wall time about 10 s on the box CPU. Checkpoint (not in git): `/workspace/archai-data/archai_v1_generator_budget_bins_smoke.pt`, SHA-256 `954cfab08e64103db499bc6171a261d29737b68915a6291bccd65acfef920cfe`. Reload reproduced samples. Training loss 1.613 → 1.388 over 300 epochs.

| Setting | Mean val acc (%) | Best val acc (%) | Param-budget satisfaction (≤ 0.8M) |
| --- | --- | --- | --- |
| Binned-ceiling generator (raw samples, n=1000) | 89.49 | 91.47 | 0.983 |
| Uniform random cells | 83.41 | 91.39 | 0.908 |
| Untrained generator | 84.81 | 91.55 | 0.889 |
| Earlier 2-d ceiling generator (same scale, previously measured) | 89.73 | — | 0.762 |
| Earlier point-estimate generator (same scale, previously measured) | 89.18 | — | 0.690 |

Raw param-budget satisfaction is **better than uniform random** (0.983 vs 0.908). Mean candidate quality is also higher than random (89.49 vs 83.41). With hard rejection sampling (1000 accepted cells, 1024 draws, yield 0.977) mean validation accuracy is 89.71 vs 82.73 for random cells that already satisfy the 0.8M budget.

Low-accuracy conditioning still produces a lower mean (53.76), so the accuracy half of the condition is not ignored.

## Ablation: rejection-aware penalty (40 extra epochs)

Same seed, corpus, and bin encoding, then 40 rejection-aware epochs (MLE on feasible in-table samples at the evaluation condition; a REINFORCE-style excess-params penalty on in-table violators). Wall time about 14 s. Checkpoint SHA-256 `82db3750d9036de2fbb8a36f71bb3356549f3222bfa963bc4ccba4383186c26c` was measured and is recorded in `ablation_penalty40.json`; that weight file was not retained after the selected (no-penalty) checkpoint was written to the canonical smoke path. Loss 1.613 → 0.717 over 340 epochs.

| Setting | Mean val acc (%) | Param-budget satisfaction (≤ 0.8M) |
| --- | --- | --- |
| Binned-ceiling + 40 penalty epochs (raw samples, n=1000) | 74.18 | 1.000 |
| Uniform random cells (same run) | 83.41 | 0.908 |

Satisfaction reached 1.0, but mean validation accuracy fell **below** random (74.18 vs 83.41). Hard-reject yield stayed 0.977, with mean validation accuracy 74.99 vs 82.73 for random feasible cells. The penalty was therefore not selected; `--penalty-epochs` defaults to 0.

## Notes

- The 2-d continuous ceiling condition (previous run) still leaked large-cell behavior (satisfaction 0.762 < random 0.915). The 8-d one-hot bin plus tight-budget oversampling is what closed that gap at this scale.
- Hard rejection remains available as a filter; at this scale the selected condition already adheres well and does not need it for satisfaction, but the filter is still the strict enforcement path if a caller requires zero violations.
