"""Run a deterministic, dependency-light search-controller smoke test."""
from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture
from archai_search.policies import RandomSearch


def candidate(channels: int) -> Architecture:
    return validate_architecture(Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=32, width=32), output_classes=10,
        generator_version="smoke", seed=7,
    ))


if __name__ == "__main__":
    policy = RandomSearch([candidate(8), candidate(16), candidate(32)], seed=7)
    seen = []
    while (item := policy.ask()) is not None:
        seen.append(item.content_hash())
    print({"evaluations": len(seen), "unique": len(set(seen)), "status": "controller_smoke_passed"})
