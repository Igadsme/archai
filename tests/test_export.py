import json
import pytest

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_compiler.export import export_architecture_json


def architecture():
    return Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=8), Node(id="output", op="output", channels=8)],
                        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
                        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10)


def test_canonical_architecture_export(tmp_path):
    path = tmp_path / "architecture.json"
    identifier = export_architecture_json(architecture(), path)
    payload = json.loads(path.read_text())
    assert payload["architecture_id"] == identifier
    assert payload["schema_version"] == "1.0"


def test_safetensors_export_is_explicitly_dependency_gated(tmp_path):
    torch = pytest.importorskip("torch")
    from archai_compiler.pytorch_compiler import compile_architecture
    from archai_compiler.export import export_safetensors, model_fingerprint
    model = compile_architecture(architecture())
    model(torch.randn(1, 3, 8, 8))
    assert len(model_fingerprint(model)) == 64
    pytest.importorskip("safetensors")
    path = tmp_path / "weights.safetensors"
    assert len(export_safetensors(model, path)) == 64
    assert path.exists()
