from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_is_a_single_free_web_service():
    text = (ROOT / "render.yaml").read_text()
    assert "plan: free" in text
    assert "type: web" in text
    assert "ARCHAI_EMBED_WORKER" in text
    assert "ARCHAI_REQUIRE_API_KEY" in text
    assert "alembic upgrade head" in text
    assert "pip install '.[platform]'" in text
    assert ".[ml" not in text
    assert "natsbench-tss-cifar10-256/cells.jsonl" in text
    assert "4a4b956ad6ae53b9d0b17fcf04b4935d17db030661afe23bbdb111c27ac5a148" in text
    assert "type: worker" not in text
    assert "type: cron" not in text
    assert "type: pspg" not in text and "type: redis" not in text
    # Official archive must not be the hosted dataset.
    assert "NATS-tss-v1_0-3ffb9-simple" not in text


def test_free_tier_plan_documents_official_sources_and_card_risks():
    text = (ROOT / "docs/deploy/FREE_TIER_PLAN.md").read_text()
    for url in (
        "https://www.kaggle.com/docs/efficient-gpu-usage",
        "https://www.kaggle.com/docs/notebooks",
        "https://huggingface.co/docs/hub/en/storage-limits",
        "https://huggingface.co/pricing",
        "https://vercel.com/docs/plans/hobby",
        "https://render.com/docs/free",
        "https://neon.com/docs/introduction/plans",
        "https://upstash.com/docs/redis/overall/billing",
    ):
        assert url in text
    assert "No free Background Workers" in text or "no free Background Workers" in text.lower() or "No free background workers" in text
    assert "cannot have free databases" in text
    assert "30 days" in text  # Render Postgres expiry
    assert "Do not add a payment method" in text or "Do not add a card" in text


def test_vercel_config_and_hosting_runbook_exist():
    vercel = (ROOT / "apps/web/vercel.json").read_text()
    assert "npm ci" in vercel
    assert "npm run build" in vercel
    runbook = (ROOT / "docs/deploy/HOSTING_RUNBOOK.md").read_text()
    assert "Do not add a payment method" in runbook
    assert "Root Directory" in runbook
    assert "NEXT_PUBLIC_ARCHAI_API_URL" in runbook
    assert "ARCHAI_API_KEY_SHA256" in runbook
    env = (ROOT / "docs/deploy/ENV.md").read_text()
    assert "ARCHAI_REQUIRE_API_KEY" in env
    assert "ARCHAI_CORS_ORIGINS" in env


def test_model_card_marks_gpu_placeholders_and_keeps_measured_smoke_fields():
    card = (ROOT / "MODEL_CARD.md").read_text()
    assert "PLACEHOLDER (not yet measured)" in card
    assert "0.983" in card
    assert "89.49" in card
    assert "cpu smoke" in card.lower() or "CPU smoke" in card


def test_kaggle_notebook_and_runbook_describe_official_checksums():
    notebook = (ROOT / "notebooks/archai_v1_kaggle_train.ipynb").read_text()
    runbook = (ROOT / "docs/deploy/KAGGLE_RUNBOOK.md").read_text()
    digest = "580fd8f3425fed9f495640b0f12ccb7744f89dec7aff263bd75aed37ab0b8bb6"
    assert digest in notebook and digest in runbook
    assert "Save & Run All" in runbook
    assert "scripts/kaggle_train_archai_v1.py" in notebook
