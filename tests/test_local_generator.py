import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from archai_core.schema import TensorSpec

HAS_TORCH = importlib.util.find_spec("torch") is not None
pytestmark = pytest.mark.skipif(not HAS_TORCH, reason="torch is not installed")
ROOT = Path(__file__).resolve().parents[1]


def test_budget_encoding_picks_the_largest_bin_under_the_budget():
    from archai_generator.local_corpus import CONDITION_DIM, bin_for_budget, encode_budget
    assert encode_budget(None) == (0.0,) * CONDITION_DIM
    assert bin_for_budget(1 / 3) == 1 and bin_for_budget(0.34) == 1 and bin_for_budget(0.32) == 0
    assert bin_for_budget(0.01) == 0 and bin_for_budget(5.0) == 5
    code = encode_budget(0.5)
    assert code[0] == 1.0 and code[1] == pytest.approx(0.5) and code[2:].index(1.0) == 2


def test_corpus_labels_are_exact_analytical_flops():
    from archai_compiler.metrics import analytical_metrics
    from archai_generator.local_corpus import build_corpus, chain, reference_flops
    spec = TensorSpec(channels=3, height=16, width=16)
    corpus = build_corpus(32, seed=1, spec=spec)
    reference = reference_flops(8, spec, 10)
    for row in corpus[:8]:
        assert analytical_metrics(chain(row["ops"], spec, 10)).flops == row["flops"]
        assert row["flops_fraction"] == pytest.approx(row["flops"] / reference)
    assert max(row["flops_fraction"] for row in corpus) <= 1.0


def test_small_training_run_learns_to_respect_a_tight_budget():
    sys.path.insert(0, str(ROOT))
    from archai_generator.local_corpus import budget_adherence

    from scripts.train_generator_local import train
    model, _corpus, history, _seconds, spec = train(corpus_size=1024, epochs=150, seed=0, lr=3e-3, hidden_dim=32)
    assert history[-1] < history[0]
    [row] = budget_adherence(model, budgets=[1 / 3], samples=128, length=8, spec=spec, output_classes=10, seed=7)
    assert row["within_budget_conditioned"] > row["within_budget_unconditioned"] + 0.15


def test_script_writes_a_checkpoint_the_api_serves_with_budget_conditioning(tmp_path, monkeypatch):
    checkpoint, report = tmp_path / "local.pt", tmp_path / "report.json"
    subprocess.run([sys.executable, str(ROOT / "scripts/train_generator_local.py"), "--checkpoint", str(checkpoint),
                    "--report", str(report), "--corpus-size", "512", "--epochs", "60", "--eval-samples", "32"],
                   check=True, cwd=ROOT, capture_output=True)
    payload = json.loads(report.read_text())
    assert payload["metadata"]["condition_encoding"]["name"] == "analytical_flops_budget_v1"
    assert payload["metadata"]["scale"] == "local_cpu" and len(payload["budget_adherence"]) == 4

    from archai_api.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setenv("ARCHAI_GENERATOR_CHECKPOINT", str(checkpoint))
    for name in ("ARCHAI_API_KEY", "ARCHAI_API_KEY_SHA256"):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(app)
    plain = client.post("/v1/architectures/generate", json={"count": 2, "seed": 0}).json()
    assert plain["condition_source"] == "none" and plain["count"] == 2
    budget = payload["metadata"]["condition_encoding"]["reference_flops_at_trained_spec"] // 2
    budgeted = client.post("/v1/architectures/generate", json={"count": 2, "seed": 0,
                                                              "constraints": {"max_flops": budget}})
    assert budgeted.status_code == 200, budgeted.text
    body = budgeted.json()
    assert body["condition_source"].startswith("max_flops") and body["condition"][0] == 1.0
    assert body["metadata"]["label"].startswith("local CPU generator")
