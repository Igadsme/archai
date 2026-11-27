"""Host and GPU telemetry read from the running process's machine.

Every value comes from a live system interface: `/proc` and `os` for the host, NVML
(`pynvml` / `nvidia-ml-py`) for NVIDIA GPUs, and `torch.cuda` as a fallback when NVML is not
installed. Nothing is estimated. When no GPU is visible the result says so and why.
"""
from __future__ import annotations

import os
import platform
import resource
import socket
from datetime import UTC, datetime
from pathlib import Path


def _meminfo() -> dict[str, int] | None:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    values: dict[str, int] = {}
    for line in path.read_text().splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name] = int(parts[0]) * 1024 if len(parts) > 1 and parts[1] == "kB" else int(parts[0])
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    if total is None or available is None:
        return None
    return {"total_bytes": total, "available_bytes": available, "used_bytes": total - available}


def _cgroup_memory_limit() -> int | None:
    for candidate in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        path = Path(candidate)
        if path.is_file():
            raw = path.read_text().strip()
            if raw.isdigit() and int(raw) < 1 << 60:
                return int(raw)
    return None


def host_telemetry() -> dict:
    try:
        load = list(os.getloadavg())
    except (AttributeError, OSError):
        load = None
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if platform.system() == "Darwin" else rss * 1024
    return {"hostname": socket.gethostname(), "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "load_average": load, "memory": _meminfo(), "cgroup_memory_limit_bytes": _cgroup_memory_limit(),
            "process_peak_rss_bytes": rss_bytes}


def _nvml_devices() -> tuple[list[dict] | None, str | None]:
    try:
        import pynvml
    except ImportError:
        return None, "pynvml (nvidia-ml-py) is not installed"
    try:
        pynvml.nvmlInit()
    except Exception as exc:  # NVMLError when no driver is present
        return None, f"NVML could not initialise: {exc}"
    try:
        devices = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)

            def optional(read):
                try:
                    return read()
                except Exception:
                    return None
            temperature = optional(lambda h=handle: pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
            power_mw = optional(lambda h=handle: pynvml.nvmlDeviceGetPowerUsage(h))
            devices.append({"index": index, "name": name.decode() if isinstance(name, bytes) else str(name),
                            "memory_total_bytes": int(memory.total), "memory_used_bytes": int(memory.used),
                            "utilization_percent": int(utilization.gpu),
                            "memory_utilization_percent": int(utilization.memory),
                            "temperature_c": temperature,
                            "power_watts": round(power_mw / 1000, 1) if power_mw is not None else None})
        return devices, None
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def _torch_devices() -> tuple[list[dict] | None, str]:
    try:
        import torch
    except ImportError:
        return None, "torch is not installed"
    mps = bool(getattr(getattr(torch.backends, "mps", None), "is_available", lambda: False)())
    if not torch.cuda.is_available():
        reason = f"torch {torch.__version__} reports no CUDA device (torch.cuda.is_available() is False)"
        if mps:
            reason += "; Apple MPS is available but exposes no utilisation or memory telemetry"
        return None, reason
    devices = []
    for index in range(torch.cuda.device_count()):
        free, total = torch.cuda.mem_get_info(index)
        devices.append({"index": index, "name": torch.cuda.get_device_name(index),
                        "memory_total_bytes": int(total), "memory_used_bytes": int(total - free),
                        "utilization_percent": None, "memory_utilization_percent": None,
                        "temperature_c": None, "power_watts": None})
    return devices, "utilisation, temperature and power need NVML (pip install nvidia-ml-py)"


def gpu_telemetry() -> dict:
    devices, nvml_reason = _nvml_devices()
    if devices:
        return {"available": True, "source": "nvml", "devices": devices, "reason": None}
    torch_devices, torch_reason = _torch_devices()
    if torch_devices:
        return {"available": True, "source": "torch.cuda", "devices": torch_devices, "reason": torch_reason}
    reasons = [reason for reason in (nvml_reason, torch_reason) if reason]
    return {"available": False, "source": None, "devices": [], "reason": "No GPU: " + "; ".join(reasons)}


def snapshot() -> dict:
    return {"measured_at": datetime.now(UTC).isoformat(), "host": host_telemetry(), "gpu": gpu_telemetry()}
