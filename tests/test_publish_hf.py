from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import publish_hf

ROOT = Path(__file__).resolve().parents[1]


def test_publish_hf_dry_run_does_not_call_the_hub(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts"
    artifact.mkdir()
    checkpoint = artifact / "generator.pt"
    checkpoint.write_bytes(b"not-a-real-checkpoint")
    metrics = artifact / "metrics.json"
    metrics.write_text("{}\n")
    # A decoy token must not be used in dry-run.
    monkeypatch.setenv("HF_TOKEN", "hf_this_is_not_a_real_token_and_must_not_be_sent")

    def fail_upload(*_args, **_kwargs):
        raise AssertionError("dry-run must not import or call the Hub API")

    monkeypatch.setattr(publish_hf, "execute_upload", fail_upload)
    code = publish_hf.main([
        "--artifact-dir", str(artifact),
        "--model-card", str(ROOT / "MODEL_CARD.md"),
        "--repo-id", "igadsme/archai-v1-dry-run",
        "--dry-run",
    ])
    assert code == 0


def test_publish_hf_plan_is_private_by_default_and_lists_checksums(tmp_path, capsys, monkeypatch):
    artifact = tmp_path / "artifacts"
    artifact.mkdir()
    (artifact / "generator.pt").write_bytes(b"abc")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    code = publish_hf.main([
        "--artifact-dir", str(artifact),
        "--model-card", str(ROOT / "MODEL_CARD.md"),
        "--repo-id", "example/archai-v1",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["private"] is True
    assert payload["dry_run"] is True
    assert payload["api_called"] is False
    assert payload["token_used"] is False
    assert payload["token_present"] is False
    names = {row["path"] for row in payload["files"]}
    assert "generator.pt" in names
    assert "README.md" in names
    assert all(len(row["sha256"]) == 64 for row in payload["files"])


def test_publish_hf_execute_without_token_exits(tmp_path, monkeypatch):
    artifact = tmp_path / "artifacts"
    artifact.mkdir()
    (artifact / "generator.pt").write_bytes(b"abc")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="HF_TOKEN"):
        publish_hf.main(["--artifact-dir", str(artifact), "--execute"])
