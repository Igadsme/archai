"""Single registry of benchmark search policies shared by scripts, workers and the API."""
from __future__ import annotations

from .learned_search import (
    IndexGeneratorGuided,
    IndexParetoEvolution,
    IndexPredictorGuided,
    IndexREINFORCE,
)
from .search import IndexBayesianOptimization, IndexRandomSearch, IndexRegularizedEvolution

POLICIES: dict[str, dict] = {
    "random": {"cls": IndexRandomSearch, "params": (), "requires": (), "label": "Random search",
               "description": "Uniform sampling without replacement."},
    "evolution": {"cls": IndexRegularizedEvolution, "params": ("population_size", "sample_size"), "requires": (),
                  "label": "Regularized evolution", "description": "Aging evolution with tournament selection."},
    "reinforce": {"cls": IndexREINFORCE, "params": ("learning_rate", "baseline_momentum", "max_resamples"),
                  "requires": (), "label": "REINFORCE (RL)", "description": "Per-edge policy gradient with an EMA baseline."},
    "bayesian": {"cls": IndexBayesianOptimization,
                 "params": ("warmup", "beta", "lengthscale", "noise", "candidate_pool_size"), "requires": (),
                 "label": "Bayesian optimization (GP-UCB)", "description": "Gaussian process with a Hamming kernel and UCB acquisition."},
    "predictor_guided": {"cls": IndexPredictorGuided,
                         "params": ("warmup", "refit_every", "epochs", "candidate_pool_size", "learning_rate"),
                         "requires": ("torch",), "label": "Predictor-guided (ArchAI predictor)",
                         "description": "Graph predictor refitted online; greedy screening of a candidate pool."},
    "generator_guided": {"cls": IndexGeneratorGuided,
                         "params": ("warmup", "elite_size", "finetune_every", "epochs", "samples_per_step",
                                    "learning_rate", "temperature", "learn"),
                         "requires": ("torch",), "label": "Generator-guided (ArchAI-V1 generator)",
                         "description": "Autoregressive generator fine-tuned on in-budget elites."},
    "multi_objective": {"cls": IndexParetoEvolution, "params": ("population_size", "sample_size", "cost_key"),
                        "requires": (), "label": "Multi-objective (Pareto evolution)",
                        "description": "Evolution on validation accuracy vs. parameters."},
}
ALGORITHMS = tuple(POLICIES)


def available(name: str) -> tuple[bool, str | None]:
    for module in POLICIES[name]["requires"]:
        try:
            __import__(module)
        except ImportError:
            return False, f"requires the '{module}' package (install the ml extra)"
    return True, None


def build_policy(adapter, indices, algorithm: str, seed: int, params: dict | None = None):
    params = dict(params or {})
    if algorithm not in POLICIES:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    unknown = sorted(set(params) - set(POLICIES[algorithm]["params"]))
    if unknown:
        raise ValueError(f"unsupported {algorithm} parameters: {', '.join(unknown)}")
    if algorithm == "random":
        return IndexRandomSearch(indices, seed=seed)
    architecture_strings = {index: adapter.architecture_string(index) for index in indices}
    return POLICIES[algorithm]["cls"](indices, architecture_strings, seed=seed, **params)


def describe() -> list[dict]:
    rows = []
    for name, spec in POLICIES.items():
        ok, reason = available(name)
        rows.append({"name": name, "label": spec["label"], "description": spec["description"],
                     "parameters": list(spec["params"]), "available": ok, "unavailable_reason": reason})
    return rows
