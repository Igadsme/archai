# NATS-Bench TSS CIFAR-10 fixture (256 cells)

**Fixture-only.** This is a derived 256-cell subset (official indices 0–255) for CI and unit tests. It is **not** the official NATS-Bench archive, must not be used for research claims, and must not be described as a full benchmark result.

Source: official NATS-Bench TSS CIFAR-10 costs and the three archive trials, taken from the local table built against the verified `-simple` tree SHA-256 `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`.

Regenerate from that table with:

```
python -c "..."  # or re-run the export used to create cells.jsonl
```

`manifest.json` records the SHA-256 of `cells.jsonl`.
