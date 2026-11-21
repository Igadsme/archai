"""Evidence-only Hugging Face Space entry point."""
from __future__ import annotations

import json
import os
from pathlib import Path


def status() -> str:
    """Return configured artifact state without claiming unobserved metrics."""
    checkpoint = os.getenv("ARCHAI_GENERATOR_CHECKPOINT")
    model_manifest = Path(os.getenv("ARCHAI_MODEL_MANIFEST", "/data/archai-models.json"))
    dataset_manifest = Path(os.getenv("ARCHAI_DATASET_MANIFEST", "/data/dataset.json"))
    lines = ["## ArchAI Studio", "", "Evidence-aware neural architecture research.", ""]
    lines.append(f"- Generator checkpoint: `{checkpoint}`" if checkpoint else "- Generator checkpoint: not configured")
    if model_manifest.exists():
        try:
            records = json.loads(model_manifest.read_text())
            lines.append(f"- Registered model artifacts: {len(records) if isinstance(records, list) else 0}")
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
