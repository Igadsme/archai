import { describe, expect, it } from "vitest"
import type { LatencyMeasurement, TelemetryResponse, TelemetrySnapshot } from "../app/lib/types"
import { buildDiagnostics } from "../app/screens/Explorer"
import { gpuRows, noGpuReasons } from "../app/studio/Telemetry"

const host = (hostname: string): TelemetrySnapshot["host"] => ({ hostname, platform: "Linux x86_64", python: "3.11", cpu_count: 4, load_average: [0.1, 0.2, 0.3], memory: null, cgroup_memory_limit_bytes: null, process_peak_rss_bytes: 1 })
const noGpu = (hostname: string): TelemetrySnapshot => ({ measured_at: "2026-11-27T23:00:00+00:00", host: host(hostname), gpu: { available: false, source: null, devices: [], reason: "No GPU: torch reports no CUDA device" } })

describe("GPU telemetry rows", () => {
  it("states every host's reason when no GPU is visible", () => {
    const data: TelemetryResponse = { api: noGpu("api-1"), workers: [{ worker_id: "w1", hostname: "worker-1", last_seen: "", telemetry: noGpu("worker-1") }, { worker_id: "w2", hostname: "worker-2", last_seen: "", telemetry: null }] }
    expect(gpuRows(data)).toEqual([])
    expect(noGpuReasons(data)).toEqual([
      "API host api-1: No GPU: torch reports no CUDA device",
      "Worker worker-1: No GPU: torch reports no CUDA device",
      "Worker worker-2: no telemetry in its heartbeat yet",
    ])
  })

  it("lists measured devices and marks fields the source does not report", () => {
    const gpu: TelemetrySnapshot = { ...noGpu("gpu-box"), gpu: { available: true, source: "torch.cuda", reason: null, devices: [{ index: 0, name: "RTX", memory_total_bytes: 8 * 1024 ** 3, memory_used_bytes: 1024 ** 3, utilization_percent: null, memory_utilization_percent: null, temperature_c: null, power_watts: null }] } }
    const rows = gpuRows({ api: noGpu("api-1"), workers: [{ worker_id: "w", hostname: "gpu-box", last_seen: "", telemetry: gpu }] })
    expect(rows).toEqual([{ host: "worker · gpu-box", source: "torch.cuda", name: "#0 RTX", utilization: "not reported", memory: "1.00 GiB / 8.00 GiB", temperature: "not reported", power: "not reported" }])
  })
})

describe("explorer latency diagnostic", () => {
  it("passes only with a stored measurement", () => {
    const doc = { id: "a", draft: false, status: "ready" as const, validation: { status: "pass" as const } }
    expect(buildDiagnostics(doc, null, true, true, null).some((item) => item.code === "W_NO_LATENCY")).toBe(true)
    const latency = { p50_ms: 1.23456, batch_size: 1, device: "cpu", hardware: "x86_64 (4 threads)" } as LatencyMeasurement
    const measured = buildDiagnostics(doc, null, true, true, null, latency).find((item) => item.code === "measured_latency")
    expect(measured).toMatchObject({ level: "PASS", message: "Latency measured: p50 1.235 ms (batch 1, cpu, x86_64 (4 threads))" })
  })
})
