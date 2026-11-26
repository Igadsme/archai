"use client"
import { Empty, PageHeader } from "../components/Shell"
import { usePoll } from "../components/usePoll"
import type { Readiness, Worker } from "../lib/types"

type Queue = { backend: string; available: boolean; queued?: number; running?: number; terminal?: number; error?: string }

export default function Infrastructure() {
  const readiness = usePoll<Readiness>("/readiness").data
  const queue = usePoll<Queue>("/v1/infrastructure/queue").data
  const workers = usePoll<{ workers: Worker[]; status: string }>("/v1/infrastructure/workers").data
  return <>
    <PageHeader eyebrow="INFRASTRUCTURE" title="Services, queue and workers" />
    <div className="cards">
      <article><span className="label">Readiness</span><strong>{readiness?.status ?? "unreachable"}</strong><small>database {readiness?.database_configured ? (readiness.database_ready ? "ready" : "down") : "not configured"}</small></article>
      <article><span className="label">Queue</span><strong>{queue?.backend ?? "—"}</strong><small>{queue ? (queue.available ? `${queue.queued ?? 0} queued · ${queue.running ?? 0} running` : `degraded: ${queue.error}`) : "unreachable"}</small></article>
      <article><span className="label">Rate limits</span><strong>{readiness?.rate_limit_backend ?? "—"}</strong><small>{readiness?.rate_limit_redis_error ?? "no Redis errors"}</small></article>
      <article><span className="label">Workers</span><strong>{workers?.workers.length ?? 0}</strong><small>{workers?.status ?? "unreachable"}</small></article>
    </div>
    <article className="panel"><h3>Worker heartbeats</h3>{!workers || workers.workers.length === 0 ? <Empty>No live worker heartbeats (stale heartbeats over 30 s are hidden).</Empty> : <ul>{workers.workers.map((worker) => <li key={worker.worker_id}><code>{worker.worker_id}</code><span>{worker.status}{worker.active_job_id ? ` · ${worker.active_job_id.slice(0, 8)}` : ""} · {new Date(worker.last_seen).toLocaleTimeString()}</span></li>)}</ul>}</article>
  </>
}
