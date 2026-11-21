from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_api_image_contains_runtime_ml_dependencies():
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "'.[ml,platform,benchmark]'" in dockerfile


def test_web_image_does_not_require_untracked_lockfile():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    assert "package-lock.json" not in dockerfile
