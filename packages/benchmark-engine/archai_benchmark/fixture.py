"""A small, committed NATS-Bench *fixture* used in CI and unit tests.

This is not the official archive. Rows are labeled fixture-only and must not be
reported as full-benchmark research results.
"""

from __future__ import annotations

import json
from pathlib import Path


class FixtureMeta:
    def __init__(self, seeds: list[int]):
        self._seeds = seeds

    def get_dataset_seeds(self, dataset: str) -> list[int]:
        return list(self._seeds)


class FixtureAPI:
    """Minimal NATS-Bench-like backend backed by a JSONL fixture."""

    def __init__(self, rows: dict[int, dict]):
        if not rows:
            raise ValueError("fixture contains no cells")
        self._rows = rows

    @classmethod
    def from_path(cls, path: str | Path) -> FixtureAPI:
        root = Path(path)
        if root.is_dir():
            manifest = root / "manifest.json"
            if manifest.exists():
                kind = json.loads(manifest.read_text()).get("kind")
                if kind != "archai_natsbench_fixture":
                    raise ValueError(f"unsupported fixture kind: {kind}")
            data_path = root / "cells.jsonl"
        else:
            data_path = root
        if data_path.suffix != ".jsonl" or not data_path.exists():
            raise FileNotFoundError(f"fixture JSONL not found: {data_path}")
        rows: dict[int, dict] = {}
        for line in data_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rows[int(row["index"])] = row
        return cls(rows)

    def __contains__(self, index: int) -> bool:
        return int(index) in self._rows

    def arch(self, architecture_index: int) -> str:
        return self._row(architecture_index)["architecture_string"]

    def get_cost_info(
        self, architecture_index: int, dataset: str, hp: int = 200
    ) -> dict[str, float]:
        row = self._row(architecture_index)
        return {
            "params": float(row["params_m"]),
            "flops": float(row["flops_m"]),
            "latency": float(row["latency_s"]),
        }

    def get_more_info(
        self, architecture_index: int, dataset: str, hp: int = 200, is_random: int | None = 0
    ) -> dict[str, float]:
        trial = self._trial(architecture_index, is_random)
        payload = {
            "test-accuracy": float(trial["test_accuracy"]),
            "train-all-time": float(trial.get("training_time_seconds") or 0.0),
        }
        if dataset != "cifar10":
            payload["valid-accuracy"] = float(trial["validation_accuracy"])
        return payload

    def query_meta_info_by_index(self, architecture_index: int, hp: int = 200) -> FixtureMeta:
        trials = self._row(architecture_index).get("trials") or []
        seeds = [int(trial.get("trial_seed", trial.get("seed", 0))) for trial in trials]
        return FixtureMeta(seeds or [0])

    def _row(self, architecture_index: int) -> dict:
        try:
            return self._rows[int(architecture_index)]
        except KeyError as exc:
            raise IndexError(f"fixture has no cell {architecture_index}") from exc

    def _trial(self, architecture_index: int, is_random: int | None) -> dict:
        trials = self._row(architecture_index).get("trials") or []
        if not trials:
            raise ValueError(f"fixture cell {architecture_index} has no trials")
        if is_random is None:
            return trials[0]
        for trial in trials:
            if int(trial.get("trial_seed", trial.get("seed", 0))) == int(is_random):
                return trial
        return trials[int(is_random) % len(trials)]


def is_fixture_path(path: str | Path) -> bool:
    root = Path(path)
    if root.is_file() and root.suffix == ".jsonl":
        return True
    if root.is_dir() and (root / "cells.jsonl").exists():
        manifest = root / "manifest.json"
        if not manifest.exists():
            return True
        try:
            return json.loads(manifest.read_text()).get("kind") == "archai_natsbench_fixture"
        except (OSError, json.JSONDecodeError, TypeError):
            return False
    return False
