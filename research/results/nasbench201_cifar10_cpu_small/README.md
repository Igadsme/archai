# nasbench201_cifar10_cpu_small: measured benchmark-lookup results

**Evidence type:** `benchmark_lookup`. These are real NATS-Bench TSS table lookups, not training and
not predictions. CPU-small scale.

- Config: `research/experiments/nasbench201_cifar10_cpu_small.json` (budget 50 queries per run, all 15,625
  cells, seeds 0–4, BO candidate pool 256, warmup 10, beta 2.0).
- Code: commit 1dae919 on `feat/complete-archai`, run 2026-11-25 ~21:50 ET on the box (CPU), 26 s wall clock in total.
- Archive: official `NATS-tss-v1_0-3ffb9-simple.tar`, SHA-256 `580fd8f3425fed9f495640b0f12ccb7744f89dec7aff263bd75aed37ab0b8bb6`
  (computed locally; no upstream SHA-256 is published). The extracted directory's `sha256_tree` is
  `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`.
- Protocol: selection on `cifar10-valid` validation accuracy (hp=200, trial seed = run seed mapped onto
  {777, 888, 999}); `cifar10` test accuracy is reported separately and never used for selection. Each run
  has a fresh query cache.

| Arm | Best validation acc. (mean, 95% bootstrap CI) | Test acc. of the selected cell (mean, CI) |
| --- | --- | --- |
| bayesian (GP-UCB) | 91.40 [91.21, 91.58] | 94.29 [94.08, 94.44] |
| evolution (regularized) | 91.26 [90.94, 91.59] | 94.07 [93.64, 94.44] |
| bayesian_no_uncertainty (ablation, beta=0) | 91.16 [90.93, 91.39] | 93.80 [93.55, 94.10] |
| evolution_no_tournament (ablation, sample_size=1) | 91.03 [90.86, 91.18] | 93.81 [93.58, 93.98] |
| random | 90.83 [90.52, 91.04] | 93.68 [93.54, 93.81] |

Five seeds per arm and overlapping intervals: this is a pipeline-level comparison, not evidence that
one arm is better. A claim would need more seeds and larger budgets, as `docs/EXPERIMENT_PROTOCOL.md` requires.
