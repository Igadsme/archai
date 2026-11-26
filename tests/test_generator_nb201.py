import pytest
from archai_benchmark.learned_search import NB201_OPS
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_sequences, load_checkpoint, save_checkpoint

from scripts.train_generator_nb201 import connected, generation_report


def test_vocabulary_generator_learns_sequences_and_reloads(tmp_path):
    config = GeneratorConfig(latent_dim=4, hidden_dim=16, max_nodes=6, condition_dim=1, vocabulary=NB201_OPS)
    model = ArchitectureGenerator(config)
    target = ["nor_conv_3x3"] * 6
    history = fit_sequences(model, [target] * 8, conditions=[(1.0,)] * 8, epochs=60, lr=1e-2, seed=0)
    assert history[-1] < history[0]
    samples = model.sample_tokens(50, steps=6, seed=1, condition=(1.0,))
    assert sum(sample == target for sample in samples) > 25
    path = tmp_path / "g.pt"
    save_checkpoint(model, path, {"kind": "generator"})
    reloaded = ArchitectureGenerator(config)
    load_checkpoint(reloaded, path)
    assert reloaded.sample_tokens(10, steps=6, seed=3, condition=(1.0,)) == model.sample_tokens(10, steps=6, seed=3, condition=(1.0,))


def test_chain_sampling_rejects_non_default_vocabularies():
    model = ArchitectureGenerator(GeneratorConfig(vocabulary=NB201_OPS))
    with pytest.raises(ValueError):
        model.sample(seed=0)
    with pytest.raises(ValueError):
        GeneratorConfig(vocabulary=("a",))


def test_cell_connectivity_and_generation_metrics():
    assert connected(["nor_conv_3x3", "none", "none", "none", "none", "skip_connect"]) is False
    assert connected(["none", "none", "none", "skip_connect", "none", "none"]) is True
    table = {tuple(["skip_connect"] * 6): {"validation_accuracy": 80.0, "params_m": 0.1},
             tuple(["nor_conv_3x3"] * 6): {"validation_accuracy": 90.0, "params_m": 1.0}}
    report = generation_report([["skip_connect"] * 6, ["nor_conv_3x3"] * 6, ["skip_connect"] * 6], table,
                               {tuple(["skip_connect"] * 6)}, params_budget_m=0.5)
    assert report["uniqueness"] == pytest.approx(2 / 3)
    assert report["novelty_vs_training_cells"] == 0.5
    assert report["constraint_satisfaction_params"] == 0.5
    assert report["candidate_quality_mean_validation_accuracy"] == 85.0
