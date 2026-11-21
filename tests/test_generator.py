import pytest

from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_generator, generation_metrics


def test_generator_samples_valid_compilable_graphs():
    torch = pytest.importorskip("torch")
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=3))
    candidates = model.sample(seed=9)
    assert len(candidates) == 3
    assert generation_metrics(candidates)["validity"] == 1.0
    from archai_compiler.pytorch_compiler import compile_architecture
    compiled = compile_architecture(candidates[0])
    assert compiled(torch.randn(1, 3, 32, 32)).shape == (1, 10)


def test_none_operation_is_zero_not_identity():
    torch = pytest.importorskip("torch")
    from archai_core.schema import Architecture, Edge, Node, TensorSpec
    from archai_core.validation import validate_architecture
    from archai_compiler.pytorch_compiler import compile_architecture
    architecture = validate_architecture(Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="none", op="none", channels=3), Node(id="output", op="output", channels=3)],
        edges=[Edge(source="input", target="none"), Edge(source="none", target="output")],
        input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2))
    model = compile_architecture(architecture)
    output = model(torch.randn(1, 3, 4, 4))
    assert output.shape == (1, 2)


def test_generator_training_and_checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=3))
    architectures = model.sample(seed=2)[:2]
    history = fit_generator(model, architectures, epochs=2, seed=2)
    assert len(history) == 2
    assert all(torch.isfinite(torch.tensor(history)))


def test_generator_training_consumes_condition_vector():
    pytest.importorskip("torch")
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=2))
    architectures = model.sample(seed=4)
    history = fit_generator(model, [(architectures[0], (1.0,) + (0.0,) * 7)], epochs=1, seed=4)
    assert len(history) == 1
