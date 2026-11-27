"""End-to-end check against a running API backed by PostgreSQL + Redis and a durable worker.

It registers the benchmark dataset, queues a benchmark search, waits for the worker to finish it,
records the outcome as `benchmark_lookup` evidence, runs a synthetic smoke-scale candidate training
job, and prints one JSON summary. It refuses to run unless `/readiness` reports a configured database
and Redis.
"""
from __future__ import annotations

import argparse
import json
import time

import httpx

CANDIDATE = {"nodes": [{"id": "input", "op": "input", "channels": 3},
                       {"id": "conv", "op": "conv3x3", "channels": 8},
                       {"id": "output", "op": "output", "channels": 8}],
             "edges": [{"source": "input", "target": "conv"}, {"source": "conv", "target": "output"}],
             "input_spec": {"channels": 3, "height": 8, "width": 8}, "output_classes": 10}


def wait_for_job(client: httpx.Client, job_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/v1/jobs/{job_id}").raise_for_status().json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.5)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument("--dataset-checksum", required=True)
    parser.add_argument("--dataset-uri", required=True)
    parser.add_argument("--algorithm", default="bayesian")
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--indices", default="0:256", help="start:stop range of benchmark indices")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--code-revision", default="working-tree")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    headers = {"x-api-key": args.api_key} if args.api_key else {}
    start, stop = (int(value) for value in args.indices.split(":"))
    with httpx.Client(base_url=args.api, headers=headers, timeout=30) as client:
        readiness = client.get("/readiness").raise_for_status().json()
        if not (readiness["database_configured"] and readiness["database_ready"]
                and readiness["durable_worker_configured"]):
            raise SystemExit(f"live services are not ready: {readiness}")
        dataset = {"dataset_id": "natsbench-tss", "version": "v1_0-3ffb9-simple",
                   "checksum": args.dataset_checksum, "uri": args.dataset_uri, "license": "MIT"}
        registered = client.post("/v1/datasets", json=dataset)
        if registered.status_code not in (200, 409):
            registered.raise_for_status()
        search = client.post("/v1/searches", json={
            "algorithm": args.algorithm, "dataset_id": "cifar10", "budget_evaluations": args.budget,
            "seed": args.seed, "indices": list(range(start, stop))}).raise_for_status().json()
        client.post(f"/v1/searches/{search['search_id']}/start").raise_for_status()
        search_job = wait_for_job(client, search["search_id"], args.timeout)
        if search_job["status"] != "succeeded":
            raise SystemExit(f"search job failed: {search_job}")
        result = search_job["payload"].get("result", {})
        from archai_benchmark.nasbench201 import architecture_from_string
        from archai_core.schema import TensorSpec
        encoding = result.get("selected_architecture_string")
        architecture_id = None
        if encoding:
            cell = architecture_from_string(encoding, input_spec=TensorSpec(channels=3, height=32, width=32))
            created = client.post("/v1/architectures", json=cell.model_dump(mode="json"))
            created.raise_for_status()
            architecture_id = created.json()["hash"]
        experiment = None
        if architecture_id:
            experiment = client.post("/v1/experiments", json={
                "architecture_id": architecture_id, "evidence_type": "benchmark_lookup",
                "dataset_id": dataset["dataset_id"], "dataset_version": dataset["version"],
                "dataset_checksum": args.dataset_checksum, "hardware": "cpu-box",
                "code_revision": args.code_revision, "seed": args.seed,
                "metrics": {"validation_accuracy": result["selected_validation_accuracy"],
                            "test_accuracy": result["held_out_test_accuracy"]}}).raise_for_status().json()
        training = client.post("/v1/training", json={"kind": "candidate", "payload": {
            "architecture": CANDIDATE, "dataset": "synthetic", "epochs": 1, "train_samples": 16,
            "validation_samples": 8, "batch_size": 4, "seed": args.seed,
            "checkpoint_path": "/tmp/archai-live-candidate.pt"}}).raise_for_status().json()
        training_job = wait_for_job(client, training["job_id"], args.timeout)
        summary = {"readiness": readiness, "search_job_status": search_job["status"],
                   "search_result": {key: result.get(key) for key in (
                       "algorithm", "queries", "selected_index", "selected_validation_accuracy",
                       "held_out_test_accuracy", "archive_sha256")},
                   "experiment_id": experiment and experiment["experiment_id"],
                   "experiment_persisted": bool(experiment) and client.get(
                       f"/v1/experiments/{experiment['experiment_id']}").status_code == 200,
                   "training_job_status": training_job["status"],
                   "training_evidence": "synthetic smoke-scale data (not a research result)",
                   "workers": client.get("/v1/infrastructure/workers").json()}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if search_job["status"] == "succeeded" and training_job["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
