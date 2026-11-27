import importlib.util
import sys

import pytest
from archai_api import main as api_main
from archai_api.main import app
from archai_shared import telemetry
from archai_shared.jobs import InMemoryJobStore
from fastapi.testclient import TestClient

client = TestClient(app)
HAS_TORCH = importlib.util.find_spec("torch") is not None


def architecture():
    return {"nodes": [{"id": "input", "op": "input", "channels": 3},
                      {"id": "conv", "op": "conv3x3", "channels": 8},
                      {"id": "output", "op": "output", "channels": 8}],
            "edges": [{"source": "input", "target": "conv"}, {"source": "conv", "target": "output"}],
            "input_spec": {"channels": 3, "height": 8, "width": 8}, "output_classes": 10}


@pytest.fixture(autouse=True)
def open_mode(monkeypatch):
    for name in ("ARCHAI_API_KEY", "ARCHAI_API_KEY_SHA256", "ARCHAI_PROTECT_READS"):
        monkeypatch.delenv(name, raising=False)


def test_telemetry_reports_live_host_values_and_explains_a_missing_gpu(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", None)
    if HAS_TORCH:
        import torch
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    body = client.get("/v1/infrastructure/telemetry").json()
    host = body["api"]["host"]
    assert host["cpu_count"] and host["cpu_count"] > 0
    assert body["api"]["gpu"]["available"] is False
    assert body["api"]["gpu"]["reason"].startswith("No GPU:")
    assert body["api"]["gpu"]["devices"] == []
    assert body["workers"] == []


def test_gpu_telemetry_reads_nvml_when_present(monkeypatch):
    class Memory:
        total, used = 16 * 2**30, 4 * 2**30

    class Rates:
        gpu, memory = 37, 12

    class FakeNvml:
        NVML_TEMPERATURE_GPU = 0
        nvmlInit = staticmethod(lambda: None)
        nvmlShutdown = staticmethod(lambda: None)
        nvmlDeviceGetCount = staticmethod(lambda: 1)
        nvmlDeviceGetHandleByIndex = staticmethod(lambda index: index)
        nvmlDeviceGetName = staticmethod(lambda handle: b"Test GPU")
        nvmlDeviceGetMemoryInfo = staticmethod(lambda handle: Memory())
        nvmlDeviceGetUtilizationRates = staticmethod(lambda handle: Rates())
        nvmlDeviceGetTemperature = staticmethod(lambda handle, sensor: 61)
        nvmlDeviceGetPowerUsage = staticmethod(lambda handle: 123456)

    monkeypatch.setitem(sys.modules, "pynvml", FakeNvml)
    gpu = telemetry.gpu_telemetry()
    assert gpu["available"] and gpu["source"] == "nvml"
    device = gpu["devices"][0]
    assert device == {"index": 0, "name": "Test GPU", "memory_total_bytes": 16 * 2**30,
                      "memory_used_bytes": 4 * 2**30, "utilization_percent": 37,
                      "memory_utilization_percent": 12, "temperature_c": 61, "power_watts": 123.5}


def test_retry_requeues_failed_jobs_with_the_same_inputs(monkeypatch):
    store = InMemoryJobStore()
    monkeypatch.setattr(api_main, "_jobs", store)
    job = store.create("training", {"architecture": architecture(), "epochs": 2})
    store.transition(job.job_id, "running")
    store.update_payload(job.job_id, {**job.payload, "progress": {"phase": "training"}})
    store.transition(job.job_id, "failed", "boom")
    response = client.post(f"/v1/jobs/{job.job_id}/retry")
    assert response.status_code == 200, response.text
    retried = response.json()
    assert retried["status"] == "queued" and retried["kind"] == "training"
    assert retried["payload"] == {"architecture": architecture(), "epochs": 2, "retry_of": job.job_id}
    assert store.get(job.job_id).payload["retried_as"] == retried["job_id"]
    assert client.post(f"/v1/jobs/{retried['job_id']}/retry").status_code == 409
    assert client.post("/v1/jobs/missing/retry").status_code == 404


def test_retry_of_a_search_needs_the_durable_worker(monkeypatch):
    store = InMemoryJobStore()
    monkeypatch.setattr(api_main, "_jobs", store)
    job = store.create("search", {"algorithm": "random", "budget_evaluations": 4, "dataset_id": "cifar10"})
    store.transition(job.job_id, "cancelled")
    assert client.post(f"/v1/jobs/{job.job_id}/retry").status_code == 503
    monkeypatch.setattr(api_main, "_redis_is_ready", lambda: True)
    retried = client.post(f"/v1/jobs/{job.job_id}/retry").json()
    assert client.get(f"/v1/searches/{retried['job_id']}").json()["retry_of"] == job.job_id


@pytest.mark.skipif(not HAS_TORCH, reason="torch is not installed")
def test_latency_is_measured_stored_and_listed():
    architecture_id = client.post("/v1/architectures", json=architecture()).json()["hash"]
    response = client.post(f"/v1/architectures/{architecture_id}/latency",
                           json={"batch_size": 2, "warmup": 1, "iterations": 5})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["evidence_type"] == "measured_latency" and result["device"] == "cpu"
    assert result["iterations"] == 5 and result["output_shape"] == [2, 10]
    assert 0 < result["min_ms"] <= result["p50_ms"] <= result["max_ms"]
    listed = client.get(f"/v1/architectures/{architecture_id}/latency").json()["items"]
    assert listed[0]["measurement_id"] == result["measurement_id"]


@pytest.mark.skipif(not HAS_TORCH, reason="torch is not installed")
def test_latency_refuses_cuda_without_a_gpu(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    architecture_id = client.post("/v1/architectures", json=architecture()).json()["hash"]
    response = client.post(f"/v1/architectures/{architecture_id}/latency", json={"device": "cuda"})
    assert response.status_code == 503
    assert client.post("/v1/architectures/unknown/latency").status_code == 404
