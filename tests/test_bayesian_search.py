from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_search.policies import BayesianOptimization


def candidate(channels):
    return Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
                        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
                        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10)


def test_bayesian_pool_is_seeded_deduplicated_and_updateable():
    candidates = [candidate(4), candidate(8), candidate(16), candidate(32)]
    left = BayesianOptimization(candidates, seed=9, warmup=1)
    right = BayesianOptimization(candidates, seed=9, warmup=1)
    first_left, first_right = left.ask(), right.ask()
    assert first_left.content_hash() == first_right.content_hash()
    left.tell(first_left, 0.4)
    assert left.ask().content_hash() not in left.observations
