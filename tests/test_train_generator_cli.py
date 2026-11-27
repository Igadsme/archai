import json

from archai_core.schema import Architecture, Edge, Node, TensorSpec

from scripts.train_generator import load_examples
from scripts.train_generator import main as train_generator_main


def architecture():
    return Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=3), Node(id="output", op="output", channels=3)],
                        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
                        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10)


def test_generator_corpus_loader_reads_conditions(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"architecture": architecture().model_dump(), "condition": [1.0] + [0.0] * 7}) + "\n")
    examples = load_examples(corpus)
    assert len(examples) == 1
    assert examples[0][1][0] == 1.0


def test_generator_training_cli_writes_checkpoint_and_report(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("torch")
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"architecture": architecture().model_dump(),
        "condition": [1.0] + [0.0] * 7}) + "\n")
    checkpoint = tmp_path / "generator.pt"
    report = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["train_generator", "--corpus", str(corpus),
        "--checkpoint", str(checkpoint), "--report", str(report), "--epochs", "1", "--seed", "5"])
    assert train_generator_main() == 0
    assert checkpoint.exists()
    payload = json.loads(report.read_text())
    assert len(payload["checkpoint_sha256"]) == 64
    assert payload["metadata"]["conditional"] is True
    assert payload["generation_metrics"]["validity"] == 1.0
