"use client"
import { usePoll } from "../components/usePoll"
import type { GpuTelemetry, TelemetrySnapshot, TelemetryResponse } from "../lib/types"
import { formatBytes, Loaded, shortId, Status, Unavailable } from "./ui"

export type GpuRow = { host: string; source: string; name: string; utilization: string; memory: string; temperature: string; power: string }

const pct = (value: number | null | undefined) => typeof value === "number" ? `${value}%` : "not reported"

/** One row per GPU reported by the API host or a worker; empty when no GPU is visible anywhere. */
export function gpuRows(data: TelemetryResponse | null): GpuRow[] {
  if (!data) return []
  const hosts: [string, GpuTelemetry | undefined][] = [[`api · ${data.api.host.hostname}`, data.api.gpu],
    ...data.workers.map((worker) => [`worker · ${worker.hostname}`, worker.telemetry?.gpu] as [string, GpuTelemetry | undefined])]
  return hosts.flatMap(([host, gpu]) => gpu?.available ? gpu.devices.map((device) => ({
    host, source: gpu.source ?? "—", name: `#${device.index} ${device.name}`, utilization: pct(device.utilization_percent),
    memory: `${formatBytes(device.memory_used_bytes)} / ${formatBytes(device.memory_total_bytes)}`,
    temperature: typeof device.temperature_c === "number" ? `${device.temperature_c} °C` : "not reported",
    power: typeof device.power_watts === "number" ? `${device.power_watts} W` : "not reported",
  })) : [])
}

/** Reasons each host gave for having no GPU, so the "no GPU" state is explicit rather than assumed. */
export function noGpuReasons(data: TelemetryResponse | null): string[] {
  if (!data) return []
  const reasons = [data.api.gpu.available ? null : `API host ${data.api.host.hostname}: ${data.api.gpu.reason}`]
  for (const worker of data.workers) {
    if (!worker.telemetry) reasons.push(`Worker ${worker.hostname}: no telemetry in its heartbeat yet`)
    else if (!worker.telemetry.gpu.available) reasons.push(`Worker ${worker.hostname}: ${worker.telemetry.gpu.reason}`)
  }
  return reasons.filter((reason): reason is string => !!reason)
}

export function useTelemetry(intervalMs = 10_000) {
  return usePoll<TelemetryResponse>("/v1/infrastructure/telemetry", intervalMs)
}

export function GpuTelemetryView({ poll }: { poll: ReturnType<typeof useTelemetry> }) {
  return <Loaded poll={poll} label="GPU telemetry">{(data) => {
    const rows = gpuRows(data)
    const reasons = noGpuReasons(data)
    return <>
      {rows.length ? <div className="table-wrap"><table aria-label="GPU telemetry"><thead><tr><th>HOST</th><th>GPU</th><th>UTIL.</th><th>MEMORY</th><th>TEMP.</th><th>POWER</th><th>SOURCE</th></tr></thead><tbody>
        {rows.map((row) => <tr key={`${row.host}-${row.name}`}><td>{row.host}</td><td>{row.name}</td><td className="mono">{row.utilization}</td><td className="mono">{row.memory}</td><td className="mono">{row.temperature}</td><td className="mono">{row.power}</td><td className="mono">{row.source}</td></tr>)}
      </tbody></table></div> : null}
      {reasons.length ? <Unavailable feature={rows.length ? "GPU on some hosts" : "GPU — none detected"} reason={reasons.join(" · ")} /> : null}
      <p className="panel-note">Live readings at {data.api.measured_at.replace("T", " ").slice(0, 19)} UTC (NVML, else torch.cuda). Workers report with their heartbeat.</p>
    </>
  }}</Loaded>
}

const usage = (snapshot: TelemetrySnapshot) => {
  const memory = snapshot.host.memory
  return memory ? `${formatBytes(memory.used_bytes)} / ${formatBytes(memory.total_bytes)}` : "not reported"
}

export function HostMetricsView({ poll }: { poll: ReturnType<typeof useTelemetry> }) {
  return <Loaded poll={poll} label="host metrics">{(data) => {
    const hosts: [string, string, TelemetrySnapshot | null | undefined][] = [["API", data.api.host.hostname, data.api],
      ...data.workers.map((worker) => ["Worker", `${worker.hostname} · ${shortId(worker.worker_id, 8)}`, worker.telemetry] as [string, string, TelemetrySnapshot | null | undefined])]
    return <div className="table-wrap"><table aria-label="Host metrics"><thead><tr><th>ROLE</th><th>HOST</th><th>CPUS</th><th>LOAD (1/5/15 MIN)</th><th>MEMORY USED</th><th>GPU</th></tr></thead><tbody>
      {hosts.map(([role, host, snapshot]) => <tr key={`${role}-${host}`}><td>{role}</td><td className="mono">{host}</td>
        {snapshot ? <><td className="mono">{snapshot.host.cpu_count ?? "—"}</td><td className="mono">{snapshot.host.load_average?.map((value) => value.toFixed(2)).join(" / ") ?? "not reported"}</td><td className="mono">{usage(snapshot)}</td>
          <td>{snapshot.gpu.available ? <Status tone="teal">{snapshot.gpu.devices.length} GPU</Status> : <Status tone="gray">NO GPU</Status>}</td></>
          : <td colSpan={4} className="muted">No telemetry reported yet.</td>}</tr>)}
    </tbody></table></div>
  }}</Loaded>
}
