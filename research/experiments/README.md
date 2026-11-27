# Experiment matrices

Each JSON file declares one matched-budget comparison: the benchmark slice, an index pool, one shared
query budget, the seeds, and the algorithms. Run it with

```bash
python scripts/run_experiment_matrix.py --config research/experiments/<name>.json \
  --benchmark-path /data/natsbench.pth --benchmark-sha256 <verified sha256> --output artifacts/experiments/<name>
```

`--dry-run` prints the planned runs without opening an archive. The runner verifies the archive checksum
once, gives every run its own query cache so cached hits never leak between algorithms, converts each
run to the record format consumed by `scripts/build_report.py`, and writes `runs.json` plus `report.json`
(requires every listed algorithm and at least `len(seeds)` seeds). No numbers exist until a verified
archive is supplied.
