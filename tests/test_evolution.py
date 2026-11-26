from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture
from archai_search.policies import RegularizedEvolution, mutate_architecture


def candidate():
    return validate_architecture(Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=3), Node(id="output", op="output", channels=3)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")], input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10))


def test_mutation_preserves_validity_and_changes_supported_op():
    parent = candidate()
    child = mutate_architecture(parent, __import__("random").Random(2))
    assert child.content_hash() != parent.content_hash()
    assert child.nodes[1].op in {"conv1x1", "conv3x3", "avg_pool3x3", "skip", "none"}


def test_evolution_uses_mutator_after_population_is_full():
    parent = candidate()
    calls = []
    def mutator(value, rng):
        calls.append(value.content_hash())
        return mutate_architecture(value, rng)
    policy = RegularizedEvolution(lambda: parent, population_size=1, sample_size=1, seed=2, mutator=mutator)
    first = policy.ask()
    policy.tell(first, 0.5)
    second = policy.ask()
    assert calls == [first.content_hash()]
    assert second.content_hash() != first.content_hash()
