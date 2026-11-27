"use client"
import { Empty, Loaded, PageHeader, Unavailable } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import type { AuditLog, DatasetItem, JobItem, Readiness, Worker } from "../lib/types"

type Queue = { backend: string; available: boolean; queued?: number; running?: number; terminal?: number; error?: string }

export default function SystemAdministration() {
  const readiness = usePoll<Readiness>("/readiness")
  const queue = usePoll<Queue>("/v1/infrastructure/queue")
  const workers = usePoll<{ configured: boolean; status: string; workers: Worker[] }>("/v1/infrastructure/workers")
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs")
  const datasets = usePoll<{ items: DatasetItem[] }>("/v1/datasets", 15000)
  const audit = usePoll<AuditLog>("/v1/audit?limit=50", 15000)
  const failed = items(jobs.data).filter((job) => job.status === "failed")
  const yes = (value: boolean | undefined) => value === undefined ? "—" : value ? "yes" : "no"
  return <>
    <PageHeader eyebrow="SYSTEM ADMINISTRATION" title="Services, queue and data" note="Read-only operational view. Changes to keys, limits and services are made in configuration, not from the Studio." />
    <div className="grid">
      <article className="panel"><h3>Readiness</h3>
        <Loaded poll={readiness}>{(data) => <table><tbody>
          <tr><th>Status</th><td>{data.status}</td></tr>
          <tr><th>Database configured / ready</th><td>{yes(data.database_configured)} / {yes(data.database_ready)}</td></tr>
          <tr><th>Durable worker queue (Redis)</th><td>{yes(data.durable_worker_configured)}</td></tr>
          <tr><th>Rate-limit backend</th><td>{data.rate_limit_backend ?? "—"}{data.rate_limit_redis_error ? ` (error: ${data.rate_limit_redis_error})` : ""}</td></tr>
        </tbody></table>}</Loaded>
      </article>
      <article className="panel"><h3>Queue</h3>
        <Loaded poll={queue}>{(data) => data.available ? <table><tbody>
          <tr><th>Backend</th><td>{data.backend}</td></tr><tr><th>Queued</th><td className="num">{data.queued}</td></tr><tr><th>Running</th><td className="num">{data.running}</td></tr><tr><th>Finished</th><td className="num">{data.terminal}</td></tr>
        </tbody></table> : <div className="errors" role="alert">Queue unavailable ({data.backend}): {data.error}</div>}</Loaded>
      </article>
      <article className="panel"><h3>Workers</h3>
        <Loaded poll={workers} isEmpty={(data) => data.workers.length === 0} empty="No workers have reported a heartbeat.">{(data) => <ul>{data.workers.map((worker) => <li key={worker.worker_id}>
          <code>{worker.hostname} · {worker.worker_id.slice(0, 8)}</code><span>{worker.status} · last seen {worker.last_seen}{worker.active_job_id ? ` · job ${worker.active_job_id.slice(0, 8)}` : ""}</span></li>)}</ul>}</Loaded>
      </article>
      <article className="panel"><h3>Failed jobs</h3>
        <Loaded poll={jobs} isEmpty={() => failed.length === 0} empty="No failed jobs.">{() => <ul>{failed.map((job) => <li key={job.job_id}><code>{job.kind} · {job.job_id.slice(0, 8)}</code><span className="error-text">{job.error}</span></li>)}</ul>}</Loaded>
      </article>
      <article className="panel wide"><h3>Registered datasets</h3>
        <Loaded poll={datasets} isEmpty={(data) => items(data).length === 0} empty="No datasets registered.">{(data) => <div className="table-scroll"><table><thead><tr><th>Dataset</th><th>Version</th><th>Checksum</th><th>License</th></tr></thead><tbody>
          {items(data).map((item) => <tr key={`${item.dataset_id}-${item.version}`}><td>{item.dataset_id}</td><td>{item.version}</td><td><code>{item.checksum.slice(0, 16)}</code></td><td>{item.license ?? "—"}</td></tr>)}</tbody></table></div>}</Loaded>
      </article>
      <article className="panel wide"><h3>Audit log (state-changing requests, newest first)</h3>
        <Loaded poll={audit} isEmpty={(data) => data.available && data.items.length === 0} empty="No write requests recorded yet.">{(data) => !data.available
          ? <Unavailable feature="audit-log viewer" reason={data.detail ?? "ARCHAI_AUDIT_LOG is not configured on the API host."} />
          : <div className="table-scroll"><table><thead><tr><th>Time (UTC)</th><th>Request</th><th>Status</th><th>Client</th><th>Key fingerprint</th><th>Request id</th></tr></thead><tbody>
            {data.items.map((event, index) => <tr key={`${event.timestamp}-${index}`}><td>{event.timestamp}</td><td><code>{event.method} {event.path}</code></td>
              <td className={event.outcome === "rejected" ? "error-text" : undefined}>{event.status} {event.outcome}</td><td>{event.client ?? "—"}</td>
              <td><code>{event.credential_fingerprint ?? "none"}</code></td><td><code>{event.request_id ?? "—"}</code></td></tr>)}
          </tbody></table></div>}</Loaded>
      </article>
      <article className="panel wide"><h3>Not available in the Studio</h3>
        <Unavailable feature="user and API-key management" reason="Single shared key from configuration (ARCHAI_API_KEY / ARCHAI_API_KEY_SHA256); there are no user accounts." />
        <Empty>Live CPU/memory metrics are not collected by the API; use host tooling.</Empty>
      </article>
    </div>
  </>
}
