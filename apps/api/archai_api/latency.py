"""Wall-clock inference latency of a compiled architecture on this API host.

The architecture is compiled with untrained (seeded) weights; latency depends on shapes and
operators, not on weight values. Results are labeled `measured_latency` with the device, thread
count and torch version they were measured with, so they are never mistaken for another host's.
"""
from __future__ import annotations

import platform
import statistics
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

_LOCK = threading.Lock()  # one measurement at a time so concurrent runs do not skew each other


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def measure_latency(architecture, *, batch_size: int = 1, warmup: int = 5, iterations: int = 30,
                    device: str = "cpu", max_seconds: float = 20.0, seed: int = 0) -> dict:
    import torch
    from archai_compiler.pytorch_compiler import compile_architecture

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("device=cuda requested but torch.cuda.is_available() is False on this host")
    if device not in {"cpu", "cuda"}:
        raise ValueError("device must be cpu or cuda")
    torch.manual_seed(seed)
    spec = architecture.input_spec
    with _LOCK:
        model = compile_architecture(architecture).eval().to(device)
        example = torch.randn(batch_size, spec.channels, spec.height, spec.width, device=device)

        def synchronize():
            if device == "cuda":
                torch.cuda.synchronize()

        timings_ms: list[float] = []
        started = time.perf_counter()
        truncated = False
        with torch.inference_mode():
            model(example)  # materialize lazily-initialized layers
            for _ in range(warmup):
                model(example)
            synchronize()
            for _ in range(iterations):
                if time.perf_counter() - started > max_seconds:
                    truncated = True
                    break
                begin = time.perf_counter()
                output = model(example)
                synchronize()
                timings_ms.append((time.perf_counter() - begin) * 1000)
    if not timings_ms:
        raise RuntimeError(f"warm-up alone exceeded the {max_seconds:.0f} s measurement limit")
    hardware = (torch.cuda.get_device_name(0) if device == "cuda"
                else f"{platform.processor() or platform.machine()} ({torch.get_num_threads()} threads)")
    return {
        "measurement_id": uuid4().hex,
        "architecture_id": architecture.content_hash(),
        "evidence_type": "measured_latency",
        "device": device, "hardware": hardware, "platform": f"{platform.system()} {platform.machine()}",
        "torch_version": torch.__version__, "threads": torch.get_num_threads(),
        "batch_size": batch_size, "warmup": warmup, "iterations_requested": iterations,
        "iterations": len(timings_ms), "truncated_by_time_limit": truncated,
        "weights": "untrained (seeded init); latency does not depend on weight values",
        "output_shape": list(output.shape) if timings_ms else None,
        "mean_ms": statistics.fmean(timings_ms), "p50_ms": _percentile(timings_ms, 0.5),
        "p90_ms": _percentile(timings_ms, 0.9), "p99_ms": _percentile(timings_ms, 0.99),
        "min_ms": min(timings_ms), "max_ms": max(timings_ms),
        "stdev_ms": statistics.stdev(timings_ms) if len(timings_ms) > 1 else 0.0,
        "throughput_samples_per_s": batch_size * 1000 / statistics.fmean(timings_ms),
        "measured_at": datetime.now(UTC).isoformat(),
    }


class InMemoryLatencyStore:
    def __init__(self):
        self._values: list[dict] = []
        self._lock = threading.Lock()

    def put(self, measurement: dict) -> dict:
        with self._lock:
            self._values.append(dict(measurement))
        return measurement

    def list(self, architecture_id: str, limit: int = 20) -> list[dict]:
        values = [value for value in self._values if value["architecture_id"] == architecture_id]
        return sorted(values, key=lambda value: value["measured_at"], reverse=True)[:limit]
