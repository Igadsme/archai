# NATS-Bench TSS CIFAR-10: full search-suite comparison (measured)

**Evidence type: `benchmark_lookup`.** Every accuracy here was read from the official NATS-Bench
TSS archive. No network was trained in these runs, and nothing is extrapolated.

## Exact configuration

- Config: `research/experiments/nasbench201_cifar10_full_suite.json`
- Code revision for every run: `2fe79d1992f544f7cdb6e43a868487f2a21e390e` (clean tree, stamped in each run record)
- Archive: `NATS-tss-v1_0-3ffb9-simple` (official source). Directory SHA-256 `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`; tar SHA-256 `580fd8f3…8bb6` (see `datasets/manifests/natsbench201.json`; no upstream SHA-256 is published)
- Search space: all 15,625 cells. Budget: **100 benchmark queries per run**, the same for every policy. **10 seeds** (0–9) per policy. Each run gets a fresh cache.
- Protocol: select on `cifar10-valid` validation accuracy (hp=200); report `cifar10` test accuracy of the selected cell. Seed *s* reads archive trial `available_trials[s % n]` (777/888/999).
- Learned policies (predictor-guided, generator-guided) start untrained and learn only from their own in-budget observations. No pretraining queries, no test data.
- Hyperparameters were fixed in the config before any run and were not tuned.
- Command:
  `python scripts/run_experiment_matrix.py --config research/experiments/nasbench201_cifar10_full_suite.json --benchmark-path <archive dir> --benchmark-sha256 183b6ad8… --output <dir>`,
  then `python scripts/build_report.py --runs runs.json --output report.json --min-seeds 10 --require-algorithm …` (all 11 variants)
  and `python scripts/summarize_matrix.py` (regret, Pareto fronts).
- Wall clock: 850 s for all 110 runs on the box CPU, shared with other jobs (see the last column).

## Results

Values are means over seeds with 95% bootstrap CIs [low, high]. Evidence type: benchmark_lookup.

| Policy | Ablation | Runs | Best validation acc. | Test acc. of selected cell | Regret vs. oracle (val.) | Hypervolume (val. × params) | Wall clock (s, all seeds) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bayesian | no | 10 | 91.59 [91.47, 91.67] | 94.28 [94.15, 94.40] | 0.106 [0.027, 0.220] | 135.27 [134.06, 136.41] | 73 |
| predictor_guided | no | 10 | 91.44 [91.19, 91.64] | 94.18 [93.90, 94.39] | 0.253 [0.055, 0.506] | 134.58 [133.23, 135.84] | 429 |
| evolution | no | 10 | 91.41 [91.23, 91.55] | 94.19 [93.98, 94.39] | 0.286 [0.147, 0.464] | 137.25 [136.70, 137.72] | 19 |
| generator_guided | no | 10 | 91.15 [91.01, 91.32] | 93.78 [93.57, 94.02] | 0.542 [0.375, 0.686] | 137.12 [136.53, 137.59] | 63 |
| reinforce | no | 10 | 91.14 [90.94, 91.33] | 94.05 [93.92, 94.17] | 0.554 [0.368, 0.757] | 137.56 [137.24, 137.82] | 19 |
| random | no | 10 | 91.03 [90.93, 91.16] | 93.78 [93.64, 93.93] | 0.662 [0.530, 0.770] | 137.50 [137.31, 137.72] | 18 |
| multi_objective | no | 10 | 90.97 [90.78, 91.17] | 93.56 [93.31, 93.79] | 0.721 [0.523, 0.915] | 137.59 [137.39, 137.78] | 21 |
| bayesian_no_uncertainty | yes | 10 | 91.49 [91.32, 91.63] | 94.02 [93.83, 94.19] | 0.208 [0.070, 0.372] | 134.70 [133.11, 136.05] | 75 |
| predictor_guided_small_pool | yes | 10 | 91.42 [91.30, 91.53] | 94.08 [94.00, 94.16] | 0.273 [0.168, 0.397] | 135.71 [134.68, 136.70] | 90 |
| evolution_no_tournament | yes | 10 | 91.12 [90.94, 91.32] | 93.70 [93.46, 93.91] | 0.571 [0.372, 0.761] | 137.58 [137.38, 137.79] | 21 |
| generator_guided_no_learning | yes | 10 | 91.09 [90.82, 91.34] | 93.81 [93.54, 94.07] | 0.608 [0.360, 0.877] | 137.49 [137.25, 137.75] | 21 |

Full-space oracle per seed (context only, never visible to any policy):

| Seed | Oracle cell | Oracle validation acc. | Its test acc. | Archive trial |
| --- | --- | --- | --- | --- |
| 0 | 6111 | 91.684 | 94.26 | 777 |
| 1 | 6111 | 91.720 | 94.68 | 888 |
| 2 | 9930 | 91.684 | 94.28 | 999 |
| 3 | 6111 | 91.684 | 94.26 | 777 |
| 4 | 6111 | 91.720 | 94.68 | 888 |
| 5 | 9930 | 91.684 | 94.28 | 999 |
| 6 | 6111 | 91.684 | 94.26 | 777 |
| 7 | 6111 | 91.720 | 94.68 | 888 |
| 8 | 9930 | 91.684 | 94.28 | 999 |
| 9 | 6111 | 91.684 | 94.26 | 777 |

Hypervolume is computed on (validation accuracy %, parameters in M) with the reference point
(0, 1.6) declared before the runs. "Regret" is the full-space oracle's validation accuracy for the
run's archive trial minus the best validation accuracy found.

## What the data supports

- The 95% CIs of GP-UCB BO (91.59 [91.47, 91.67]) and regularized evolution (91.41 [91.23, 91.55])
  do not overlap random search (91.03 [90.93, 91.16]) on best validation accuracy at 100 queries.
  The predictor-guided interval (91.44 [91.19, 91.64]) only just clears random's.
- Generator-guided (91.15), REINFORCE (91.14) and multi-objective (90.97) overlap random on best
  validation accuracy. Generator-guided also overlaps its no-learning ablation (91.09), so this run
  shows **no measurable benefit from online generator fine-tuning** at this budget.
- Ablations: removing BO's uncertainty term (β=0) and shrinking the predictor's screening pool
  (256→16) each lower the mean, but their CIs overlap the full versions. Removing evolution's
  tournament (sample size 1) lowers it to 91.12, and the CIs overlap here too.
- Hypervolume: the multi-objective policy (137.59 [137.39, 137.78]) is not distinguishable from random
  (137.50) or REINFORCE (137.56). BO and predictor-guided have *lower* hypervolume (≈135) because
  they concentrate on large, accurate cells.
- All test accuracies are reported for the validation-selected cell only and played no part in any choice.

`pareto.json` holds each run's Pareto front (validation vs. params) and the full-space front.
`runs.json` holds the full per-run records, including every evaluated index and the validation trace.
