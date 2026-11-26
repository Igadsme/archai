"""Plumbing and behavior tests for the learned / multi-objective index policies.

Scores here are synthetic (count of 3x3 convolutions), used only to exercise the
policies; no benchmark numbers are involved.
"""
import json

import pytest
from archai_benchmark.adapter import BenchmarkRecord
from archai_benchmark.learned_search import (
    NB201_OPS,
    IndexGeneratorGuided,
    IndexParetoEvolution,
    IndexPredictorGuided,
    IndexREINFORCE,
    cell_string,
    dominates,
)
from archai_benchmark.nasbench201 import parse_architecture_string

from scripts.run_benchmark_search import ALGORITHMS, build_policy, run_search
from scripts.run_experiment_matrix import run_matrix


def encoding(index):
    return cell_string([NB201_OPS[(index // 5 ** position) % 5] for position in range(6)])


POOL = list(range(5 ** 6))
STRINGS = {index: encoding(index) for index in POOL}


def score(index):
    return 10.0 * STRINGS[index].count("nor_conv_3x3")


def params(index):
    return 0.1 + 0.2 * STRINGS[index].count("nor_conv_3x3") + 0.05 * STRINGS[index].count("nor_conv_1x1")


def drive(policy, steps, with_cost=False):
    chosen = []
    for _ in range(steps):
        index = policy.ask()
        if with_cost:
            policy.tell(index, score(index), {"params_m": params(index)})
        else:
            policy.tell(index, score(index))
        chosen.append(index)
    return chosen


def test_cell_string_round_trips_through_the_parser():
    operations = ("nor_conv_3x3", "none", "skip_connect", "avg_pool_3x3", "nor_conv_1x1", "nor_conv_3x3")
    assert parse_architecture_string(cell_string(operations)).operations == operations
    with pytest.raises(ValueError):
        cell_string(operations[:5])


@pytest.mark.parametrize("factory", [
    lambda seed: IndexREINFORCE(POOL, STRINGS, seed=seed),
    lambda seed: IndexPredictorGuided(POOL, STRINGS, seed=seed, warmup=4, refit_every=4, epochs=5, candidate_pool_size=32),
    lambda seed: IndexGeneratorGuided(POOL, STRINGS, seed=seed, warmup=4, finetune_every=4, epochs=5, samples_per_step=16),
])
def test_learned_policies_are_seeded_unique_and_in_pool(factory):
    first, second = drive(factory(3), 14), drive(factory(3), 14)
    assert first == second
    assert len(set(first)) == len(first)
    assert set(first) <= set(POOL)


def test_tell_requires_a_matching_ask():
    policy = IndexREINFORCE(POOL, STRINGS, seed=0)
    with pytest.raises(ValueError):
        policy.tell(5, 1.0)


def test_reinforce_shifts_probability_toward_rewarded_operations():
    policy = IndexREINFORCE(POOL, STRINGS, seed=0, learning_rate=5.0)
    drive(policy, 300)
    conv3 = NB201_OPS.index("nor_conv_3x3")
    assert all(row[conv3] > 0.2 for row in policy.probabilities())  # uniform start is 0.2


def test_generator_guided_learning_beats_its_untrained_ablation_on_synthetic_scores():
    def mean_tail(learn):
        values = []
        for seed in range(2):
            chosen = drive(IndexGeneratorGuided(POOL, STRINGS, seed=seed, warmup=8, finetune_every=8, epochs=25,
                                                samples_per_step=64, learn=learn), 40)
            values.extend(score(index) for index in chosen[20:])
        return sum(values) / len(values)
    assert mean_tail(True) > mean_tail(False)


def test_predictor_guided_refits_and_finds_high_scores():
    policy = IndexPredictorGuided(POOL, STRINGS, seed=0, warmup=8, refit_every=4, epochs=40, candidate_pool_size=128)
    chosen = drive(policy, 24)
    assert policy.refits >= 3
    assert max(score(index) for index in chosen[8:]) >= max(score(index) for index in chosen[:8])


def test_pareto_evolution_needs_costs_and_uses_dominance():
    assert dominates((90.0, 0.5), (89.0, 0.5)) and not dominates((90.0, 0.9), (89.0, 0.5))
    policy = IndexParetoEvolution(POOL, STRINGS, seed=0, population_size=6, sample_size=3)
    index = policy.ask()
    with pytest.raises(ValueError):
        policy.tell(index, 1.0)
    policy = IndexParetoEvolution(POOL, STRINGS, seed=0, population_size=6, sample_size=3)
    chosen = drive(policy, 30, with_cost=True)
    assert len(set(chosen)) == 30


class CostAdapter:
    dataset = "cifar10"

    def architecture_string(self, index):
        return STRINGS[index]

    def query(self, index, seed=0):
        return BenchmarkRecord(index, self.dataset, seed, score(index), score(index) - 1.0, 1.0)

    def cost(self, index):
        return {"params_m": params(index), "flops_m": 1.0, "latency_s": 0.01}

    def open(self):
        return self


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_every_algorithm_runs_at_a_matched_budget_with_hypervolume(algorithm, tmp_path):
    small = {"predictor_guided": {"epochs": 3, "candidate_pool_size": 16},
             "generator_guided": {"epochs": 3, "samples_per_step": 8}}.get(algorithm, {})
    report = run_search(CostAdapter(), POOL[:400], budget=12, algorithm=algorithm, seed=1,
                        cache_path=tmp_path / "c.sqlite", params=small)
    assert report["queries"] == 12 and len(set(report["evaluated_indices"])) == 12
    assert report["hypervolume_validation_params"] > 0
    assert report["selected_on"] == "validation_accuracy"


def test_multi_objective_refuses_adapters_without_costs(tmp_path):
    class NoCost(CostAdapter):
        cost = None
    with pytest.raises(ValueError):
        run_search(NoCost(), POOL[:50], budget=5, algorithm="multi_objective", seed=0,
                   cache_path=tmp_path / "c.sqlite")


def test_unknown_learned_policy_parameters_are_rejected():
    with pytest.raises(ValueError):
        build_policy(CostAdapter(), POOL[:10], "reinforce", 0, {"population_size": 3})


def test_matrix_resume_skips_finished_runs(tmp_path):
    config = {"name": "unit", "benchmark": {"search_space": "tss", "dataset": "cifar10"},
              "indices": list(range(60)), "budget": 5, "seeds": [0, 1],
              "variants": [{"name": "random", "algorithm": "random", "params": {}, "ablation": False},
                           {"name": "multi_objective", "algorithm": "multi_objective", "params": {}, "ablation": False}]}
    run_matrix(config, CostAdapter(), tmp_path, revision="abc")
    lines = (tmp_path / "runs.partial.jsonl").read_text().splitlines()
    assert len(lines) == 4 and json.loads(lines[0])["code_revision"] == "abc"
    (tmp_path / "runs.partial.jsonl").write_text("\n".join(lines[:3]) + "\n")
    report = run_matrix(config, CostAdapter(), tmp_path, resume=True, revision="abc")
    assert report["run_count"] == 4
    assert "hypervolume_validation_params" in report["algorithms"]["multi_objective"]
