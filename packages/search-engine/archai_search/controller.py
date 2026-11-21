from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture


@dataclass(frozen=True)
class SearchConfig:
    max_evaluations: int
    seed: int = 0


@dataclass
class SearchState:
    status: str = "created"
    evaluations: int = 0
    candidates: list[dict] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)


class SearchController:
    """Crash-safe JSON state machine for the propose/validate/evaluate loop.

    The evaluator is injected so benchmark lookups and real training runs can
    share the controller without conflating their evidence types.
    """
    def __init__(self, config: SearchConfig, state_path: str | Path):
        if config.max_evaluations <= 0:
            raise ValueError("max_evaluations must be positive")
        self.config, self.state_path = config, Path(state_path)
        self.state = self._load()
        self._cancel_requested = False

    def _load(self) -> SearchState:
        if not self.state_path.exists():
            return SearchState()
        return SearchState(**json.loads(self.state_path.read_text()))

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".partial")
        temporary.write_text(json.dumps(asdict(self.state), sort_keys=True, indent=2))
        temporary.replace(self.state_path)

    def cancel(self) -> None:
        self._cancel_requested = True
        self.state.status = "cancel_requested"
        self._persist()

    def run(self, proposer: Callable[[], Architecture], evaluator: Callable[[Architecture], dict]) -> SearchState:
        if self.state.evaluations >= self.config.max_evaluations:
            return self.state
        self.state.status = "running"
        self._persist()
        seen = set(self.state.seen)
        while self.state.evaluations < self.config.max_evaluations and not self._cancel_requested:
            candidate = validate_architecture(proposer())
            architecture_id = candidate.content_hash()
            if architecture_id in seen:
                continue
            result = dict(evaluator(candidate))
            result.setdefault("architecture_id", architecture_id)
            result.setdefault("evidence_type", "measured")
            self.state.candidates.append(result)
            self.state.seen.append(architecture_id)
            seen.add(architecture_id)
            self.state.evaluations += 1
            self._persist()
        self.state.status = "cancelled" if self._cancel_requested else "completed"
        self._persist()
        return self.state
