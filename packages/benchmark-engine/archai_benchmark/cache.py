from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .adapter import BenchmarkRecord


class BenchmarkCache:
    """Local query cache with a uniqueness constraint for reproducible budgets."""
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS benchmark_queries (
            architecture_index INTEGER NOT NULL, dataset TEXT NOT NULL, seed INTEGER NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY (architecture_index, dataset, seed))""")
        self.connection.commit()

    def get(self, architecture_index: int, dataset: str, seed: int) -> BenchmarkRecord | None:
        row = self.connection.execute("SELECT payload FROM benchmark_queries WHERE architecture_index=? AND dataset=? AND seed=?",
                                      (architecture_index, dataset, seed)).fetchone()
        return BenchmarkRecord(**json.loads(row[0])) if row else None

    def put(self, record: BenchmarkRecord) -> None:
        self.connection.execute("INSERT OR REPLACE INTO benchmark_queries VALUES (?, ?, ?, ?)",
                                (record.architecture_index, record.dataset, record.seed, json.dumps(asdict(record))))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
