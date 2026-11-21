import json

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_generator.training import fit_generator
from scripts.train_generator import load_examples


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
