"""Evidence-only Hugging Face Space entry point."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def status() -> str:
    """Return configured artifact state without claiming unobserved metrics."""
    checkpoint = os.getenv("ARCHAI_GENERATOR_CHECKPOINT")
    model_manifest = Path(os.getenv("ARCHAI_MODEL_MANIFEST", "/data/archai-models.json"))
    dataset_manifest = Path(os.getenv("ARCHAI_DATASET_MANIFEST", "/data/dataset.json"))
    lines = ["## ArchAI Studio", "", "Evidence-aware neural architecture research.", ""]
    if not checkpoint:
        lines.append("- Generator checkpoint: not configured")
    elif not Path(checkpoint).is_file():
        lines.append(f"- Generator checkpoint: unavailable (`{checkpoint}`)")
    else:
        expected = os.getenv("ARCHAI_GENERATOR_CHECKPOINT_SHA256")
        actual = _sha256_file(checkpoint)
        if expected and actual == expected.lower():
            lines.append(f"- Generator checkpoint: verified (`{actual}`)")
        elif expected:
            lines.append(f"- Generator checkpoint: checksum mismatch (actual `{actual}`)")
        else:
            lines.append(f"- Generator checkpoint: present but unverified (`{actual}`)")
    if model_manifest.exists():
        try:
            records = json.loads(model_manifest.read_text())
            verified = 0
            if isinstance(records, list):
                for record in records:
                    path = record.get("path", record.get("artifact_uri")) if isinstance(record, dict) else None
                    checksum = record.get("sha256", record.get("checksum")) if isinstance(record, dict) else None
                    if path and checksum and Path(path).is_file() and _sha256_file(path) == str(checksum).lower():
                        verified += 1
            lines.append(f"- Registered model artifacts: {len(records) if isinstance(records, list) else 0} ({verified} verified)")
        except (OSError, json.JSONDecodeError):
            lines.append("- Registered model artifacts: manifest unreadable")
    else:
        lines.append("- Registered model artifacts: no manifest")
    lines.append(f"- Dataset manifest: `{dataset_manifest}`" if dataset_manifest.exists()
                 else "- Dataset manifest: not configured")
    lines.append("- Scientific metrics: not displayed until provenance-backed reports are supplied.")
    return "\n".join(lines)


try:
    import gradio as gr
except ImportError:  # allows packaging without Space dependencies
    gr = None


if gr:
    demo = gr.Interface(fn=status, inputs=None, outputs="text", title="ArchAI Studio")
    if __name__ == "__main__":
        demo.launch()
