# CPU-smoke generator with sampled budget-ceiling conditioning

Measured on 2026-11-25, 11:06 PM America/New_York. Code revision `a61f4e7`. Scale: 2000 training cells, 300 epochs, seed 0, NATS-Bench TSS CIFAR-10 trial 0 (evidence: `benchmark_lookup` for generated-cell quality; `measured_training` for the loss). Wall time about 5.3 s on the box CPU. Checkpoint (not in git): `/workspace/archai-data/archai_v1_generator_budget_ceiling_smoke.pt`, SHA-256 `524b81c82317f0ae28c34c18a1a6e278129317f02eb05645d06f1f64ecf6b9ae`.

The condition is (validation-accuracy quantile, a ceiling sampled uniformly from `[params_m, 1.6] / 1.6`) so each training cell is feasible under its budget, unlike the earlier point estimate (`params_m / 1.6`).

At the evaluation condition `(0.95, 0.8/1.6)`:

| Setting | Mean val acc (%) | Param-budget satisfaction (≤ 0.8M) |
| --- | --- | --- |
| Ceiling-conditioned generator (raw samples, n=1000) | 89.73 | 0.762 |
| Uniform random cells | 82.72 | 0.915 |
| Untrained generator | 84.42 | 0.850 |
| Earlier point-estimate generator (same scale, previously measured) | 89.18 | 0.690 |

Ceiling training improved raw satisfaction relative to the point-estimate run (0.762 vs 0.690) but it is still worse than uniform random (0.915). Quality remains higher than random. With hard rejection sampling (1000 accepted cells, 1280 draws, yield 0.781) mean validation accuracy is 89.82 vs 82.73 for random cells that already satisfy the 0.8M budget. At this CPU smoke scale, a parameter budget should be enforced by filtering, not by relying on the condition alone.
