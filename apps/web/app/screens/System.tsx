"use client"
import { items, usePoll } from "../components/usePoll"
import { apiBase } from "../lib/api"
import type { AuditLog, DatasetItem, JobItem, Readiness, Worker } from "../lib/types"
import { healthResponse, itemsResponse } from "../lib/validators"
import { useGo } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { Loaded, PageHeader, Panel, shortId, Status, Unavailable } from "../studio/ui"
import { AccessPanel } from "./AccessPanel"

type Queue = { backend: string; available: boolean; queued?: number; running?: number; terminal?: number; error?: string }
type Health = { status: string; evidence_policy?: string }

const yes = (value: boolean | undefined) => value === undefined ? "—" : value ? "YES" : "NO"

/** Service rows for the Figma service list, derived from /health and /readiness only. */
export function serviceRows(health: Health | null, readiness: Readiness | null, healthError: string | null): { name: string; state: string; ok: boolean | null; detail: string }[] {
  return [
    { name: "API (FastAPI)", state: health ? health.status.toUpperCase() : healthError ? "DOWN" : "…", ok: health ? health.status === "ok" : healthError ? false : null, detail: apiBase },
    { name: "Database", state: readiness ? (readiness.database_configured ? (readiness.database_ready ? "READY" : "NOT READY") : "IN-MEMORY") : "—", ok: readiness ? !readiness.database_configured || readiness.database_ready : null, detail: readiness?.database_configured ? "configured" : "ephemeral store" },
    { name: "Durable worker queue", state: readiness ? (readiness.durable_worker_configured ? "CONFIGURED" : "OFF") : "—", ok: readiness ? readiness.durable_worker_configured : null, detail: "Redis" },
    { name: "Rate limiter", state: readiness?.rate_limit_backend?.toUpperCase() ?? "—", ok: readiness ? !readiness.rate_limit_redis_error : null, detail: readiness?.rate_limit_redis_error ?? "" },
  ]
}

export function SystemAdmin() {
  const go = useGo()
  const health = usePoll<Health>("/health", 10_000, healthResponse)
  const readiness = usePoll<Readiness>("/readiness", 10_000)
  const queue = usePoll<Queue>("/v1/infrastructure/queue", 10_000)
  const workers = usePoll<{ configured: boolean; status: string; workers: Worker[] }>("/v1/infrastructure/workers", 10_000)
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs", 10_000, itemsResponse)
  const datasets = usePoll<{ items: DatasetItem[] }>("/v1/datasets", 30_000, itemsResponse)
  const audit = usePoll<AuditLog>("/v1/audit?limit=50", 15_000)
  const failed = items(jobs.data).filter((job) => job.status === "failed")
  const notReady = readiness.data && readiness.data.status !== "ready"

  return <div className="page">
    <PageHeader eyebrow="SYSTEM ADMINISTRATION" title="System administration" description="Operational view of the API host, plus user accounts and scoped API keys. Limits and services are changed in configuration.">
      <Status tone={readiness.data?.status === "ready" ? "teal" : readiness.error ? "red" : "amber"}>{readiness.data ? readiness.data.status.toUpperCase() : readiness.error ? "UNREACHABLE" : "CHECKING"}</Status>
    </PageHeader>
    {notReady ? <div className="system-alert" role="alert"><Icon name="alert" /><span>Readiness reports <b>{readiness.data!.status}</b>. Writes that need the database or worker may fail until it is ready.</span></div> : null}
    <div className="system-grid">
      <Panel title="Services" meta="/health · /readiness">
        <div className="service-list">{serviceRows(health.data, readiness.data, health.error).map((row) => <div key={row.name}><i className={row.ok === false ? "down" : row.ok === null ? "unknown" : ""} /><span><b>{row.name}</b><small>{row.detail}</small></span><code>{row.state}</code><span className="mono muted">{row.ok === false ? "CHECK" : ""}</span></div>)}</div>
        {health.data?.evidence_policy ? <p className="panel-note">Evidence policy: {health.data.evidence_policy}</p> : null}
      </Panel>
      <Panel title="Queue & workers" meta={queue.data?.backend?.toUpperCase() ?? "QUEUE"}>
        <Loaded poll={queue} label="queue">{(data) => data.available ? <div className="queue-strip"><span><small>QUEUED</small><b>{data.queued ?? 0}</b></span><span><small>RUNNING</small><b>{data.running ?? 0}</b></span><span><small>FINISHED</small><b>{data.terminal ?? 0}</b></span></div>
          : <Unavailable feature="job queue" reason={`${data.backend}: ${data.error ?? "not configured"}`} />}</Loaded>
        <Loaded poll={workers} label="workers" isEmpty={(data) => data.workers.length === 0} empty="No workers have reported a heartbeat.">{(data) => <div className="worker-list">{data.workers.map((worker) => <div key={worker.worker_id}><i className={worker.active_job_id ? "" : "queued"} /><code>{worker.hostname.slice(0, 10)}</code><span>{worker.active_job_id ? `job ${shortId(worker.active_job_id, 8)}` : "idle"} · seen {worker.last_seen.slice(11, 19)}</span><b>{worker.status}</b></div>)}</div>}</Loaded>
      </Panel>
      <Panel title="Failed jobs" meta={`${failed.length} FAILED`}>
        <Loaded poll={jobs} label="jobs" isEmpty={() => failed.length === 0} empty="No failed jobs.">{() => <div className="mount-list">{failed.slice(0, 12).map((job) => <div key={job.job_id}><Icon name="alert" size={13} /><span><b className="mono">{job.kind} · {job.job_id.slice(0, 8)}</b><small className="error-text">{job.error}</small></span><span /><button className="button compact" onClick={() => go("experiments", { job: job.job_id })}>Open</button></div>)}</div>}</Loaded>
      </Panel>
      <Panel title="Registered datasets" meta="/v1/datasets">
        <Loaded poll={datasets} label="datasets" isEmpty={(data) => data.items.length === 0} empty="No datasets registered.">{(data) => <div className="mount-list">{data.items.map((item) => <div key={`${item.dataset_id}-${item.version}`}><Icon name="database" size={13} /><span><b className="mono">{item.dataset_id}</b><small>{item.uri ?? ""}</small></span><code>{item.version}</code><code title={item.checksum}>{item.checksum.slice(0, 10)}</code></div>)}</div>}</Loaded>
      </Panel>
      <Panel title="Audit log" meta="STATE-CHANGING REQUESTS · NEWEST FIRST" className="span-all">
        {audit.status === 401 || audit.status === 403 ? <Unavailable feature="audit-log viewer" reason="The audit log needs an admin-scoped API key. Enter it in the sidebar (API KEY) to read state-changing requests." /> : <Loaded poll={audit} label="audit log" isEmpty={(data) => data.available && data.items.length === 0} empty="No write requests recorded yet.">{(data) => !data.available
          ? <Unavailable feature="audit-log viewer" reason={data.detail ?? "ARCHAI_AUDIT_LOG is not configured on the API host."} />
          : <div className="table-wrap"><table aria-label="Audit log"><thead><tr><th>TIME (UTC)</th><th>REQUEST</th><th>STATUS</th><th>CLIENT</th><th>KEY FINGERPRINT</th><th>REQUEST ID</th></tr></thead><tbody>
            {data.items.map((event, index) => <tr key={`${event.timestamp}-${index}`}><td className="mono">{event.timestamp}</td><td><code>{event.method} {event.path}</code></td>
              <td className={event.outcome === "rejected" ? "error-text" : undefined}>{event.status} {event.outcome}</td><td>{event.client ?? "—"}</td><td><code>{event.credential_fingerprint ?? "none"}</code></td><td><code>{event.request_id ?? "—"}</code></td></tr>)}
          </tbody></table></div>}</Loaded>}
      </Panel>
      <AccessPanel />
      <Panel title="Access & policy" meta="CONFIGURATION">
        <div className="setting-list">
          <div><span><b>API key</b><small>Entered in the sidebar; kept in sessionStorage for this browser session only and sent as x-api-key.</small></span><code>SESSION</code></div>
          <div><span><b>Database ready</b><small>From /readiness.</small></span><code>{yes(readiness.data?.database_ready)}</code></div>
          <div><span><b>Durable worker</b><small>From /readiness.</small></span><code>{yes(readiness.data?.durable_worker_configured)}</code></div>
        </div>
      </Panel>
      <Panel title="Host metrics" meta="NOT COLLECTED">
        <Unavailable feature="CPU, memory and GPU metrics" reason="The API does not collect host metrics. Use host tooling (node exporter, nvidia-smi) for live resource data." />
        <Unavailable feature="research policy editor" reason="Evidence rules are enforced in code (validation-only selection, evidence labels) and cannot be changed at runtime." />
      </Panel>
    </div>
  </div>
}
