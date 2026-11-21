# Research status

No training, benchmark lookup, or deployment is performed during repository creation. This is a reproducible implementation baseline, not evidence of a scientific result. Before making performance claims, run the experiment protocol with multiple seeds and preserve raw outputs under artifact storage.

Once a verified NATS-Bench archive is available, `scripts/train_predictor.py` is the supported entry point for a real predictor run. It requires explicit architecture indices, creates hash-disjoint train/validation/test partitions, and records that the test split was not used for selection.

`scripts/run_benchmark_search.py` runs the matched-budget random baseline. It selects the winning index using validation accuracy only and reports held-out test accuracy as a separate field.
