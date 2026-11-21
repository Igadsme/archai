# ArchAI experiment protocol

Every result must be emitted with the architecture hash, code revision, dataset checksum/version, model checkpoint hash, seed, hardware profile, wall-clock timestamps, and a distinction between `predicted`, `benchmark_lookup`, and `measured_training`.

The held-out test set is never used for candidate selection. Baselines and ArchAI use the same evaluation budget, candidate deduplication rules, seeds, and resource constraints. A report may only state superiority after repeated seeded runs with uncertainty intervals.
