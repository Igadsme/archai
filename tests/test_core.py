import pytest

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics
from archai_search.policies import pareto_frontier


def arch():
    return Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=8), Node(id="output", op="output", channels=8)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=32, width=32), output_classes=10,
    )


def test_validation_hash_is_deterministic():
    value = validate_architecture(arch())
    assert value.architecture_id == value.content_hash()
    assert value.content_hash() == validate_architecture(arch()).content_hash()


def test_cycle_is_rejected():
    value = arch().model_copy(update={"edges": [Edge(source="input", target="conv"), Edge(source="conv", target="input"), Edge(source="conv", target="output")]})
    with pytest.raises(ValidationError):
        validate_architecture(value)


def test_duplicate_edges_and_fanin_mismatch_are_rejected():
    duplicate = arch().model_copy(update={"edges": [Edge(source="input", target="conv"), Edge(source="input", target="conv"), Edge(source="conv", target="output")]})
    with pytest.raises(ValidationError, match="duplicate edges"):
        validate_architecture(duplicate)
    mismatch = Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="a", op="conv3x3", channels=8),
               Node(id="b", op="conv3x3", channels=16), Node(id="merge", op="skip", channels=8),
               Node(id="output", op="output", channels=8)],
        edges=[Edge(source="input", target="a"), Edge(source="input", target="b"),
               Edge(source="a", target="merge"), Edge(source="b", target="merge"), Edge(source="merge", target="output")],
        input_spec=TensorSpec(channels=3, height=32, width=32), output_classes=10,
    )
    with pytest.raises(ValidationError, match="fanin channel mismatch"):
        validate_architecture(mismatch)


def test_analytical_metrics_use_upstream_channels():
    value = Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="a", op="conv3x3", channels=8),
               Node(id="b", op="conv1x1", channels=16), Node(id="output", op="output", channels=16)],
        edges=[Edge(source="input", target="a"), Edge(source="a", target="b"), Edge(source="b", target="output")],
        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=10,
    )
    metrics = analytical_metrics(value)
    assert metrics.parameters == (3 * 8 * 9 + 8) + (8 * 16 + 16)


def test_compiler_handles_serialized_order_and_backward():
    torch = pytest.importorskip("torch")
    from archai_compiler.pytorch_compiler import compile_architecture
    value = arch().model_copy(update={"nodes": [arch().nodes[2], arch().nodes[1], arch().nodes[0]]})
    model = compile_architecture(value)
    output = model(torch.randn(2, 3, 32, 32))
    assert output.shape == (2, 10)
    output.sum().backward()
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_pareto_frontier():
    rows = [{"id": 1, "accuracy": .9, "params": 10}, {"id": 2, "accuracy": .91, "params": 20}, {"id": 3, "accuracy": .89, "params": 30}]
    assert {row["id"] for row in pareto_frontier(rows, ("accuracy",), ("params",))} == {1, 2}
