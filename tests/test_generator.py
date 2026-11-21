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


def test_generator_training_and_checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=3))
    architectures = model.sample(seed=2)[:2]
    history = fit_generator(model, architectures, epochs=2, seed=2)
    assert len(history) == 2
    assert all(torch.isfinite(torch.tensor(history)))
