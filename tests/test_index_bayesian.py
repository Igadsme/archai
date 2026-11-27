import pytest
from archai_benchmark.search import IndexBayesianOptimization

OPS = ("none", "skip_connect", "nor_conv_1x1", "nor_conv_3x3", "avg_pool_3x3")


def encoding(index):
    ops = [OPS[(index // 5 ** position) % 5] for position in range(6)]
    return f"|{ops[0]}~0|+|{ops[1]}~0|{ops[2]}~1|+|{ops[3]}~0|{ops[4]}~1|{ops[5]}~2|"


def score(index):
    # synthetic objective for policy plumbing only: more 3x3 convolutions is better
    return float(encoding(index).count("nor_conv_3x3"))


POOL = list(range(200))
STRINGS = {index: encoding(index) for index in POOL}


def run(seed, steps=20, **params):
    policy = IndexBayesianOptimization(POOL, STRINGS, seed=seed, **params)
    chosen = []
    for _ in range(steps):
        index = policy.ask()
        policy.tell(index, score(index))
        chosen.append(index)
    return policy, chosen


def test_bayesian_policy_is_seeded_and_never_repeats():
    _, first = run(3)
    _, second = run(3)
    assert first == second
    assert len(set(first)) == len(first)


def test_gp_posterior_interpolates_observations_with_low_uncertainty():
    policy, chosen = run(1, steps=8)
    mean, std = policy.posterior([chosen[0]])[0]
    unseen = next(index for index in POOL if index not in chosen)
    assert std < policy.posterior([unseen])[0][1]
    assert std < 0.1


def test_bayesian_beats_its_own_warmup_on_a_smooth_objective():
    _, chosen = run(0, steps=25, warmup=5)
    assert max(score(index) for index in chosen[5:]) >= max(score(index) for index in chosen[:5])


def test_bayesian_policy_validates_inputs_and_protocol():
    with pytest.raises(ValueError):
        IndexBayesianOptimization([], {})
    with pytest.raises(ValueError):
        IndexBayesianOptimization(POOL, STRINGS, beta=-1)
    policy = IndexBayesianOptimization(POOL[:2], STRINGS)
    with pytest.raises(ValueError, match="ask before tell"):
        policy.tell(0, 1.0)
    first, second = policy.ask(), policy.ask()
    assert {first, second} == {0, 1} and policy.ask() is None
