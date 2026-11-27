"use client"
import { ProjectPicker } from "../components/ProjectPicker"
import { items, usePoll } from "../components/usePoll"
import { jobProgress, progressFraction, progressLabel } from "../lib/progress"
import { ci, jobResult, splitAblations } from "../lib/results"
import type { ArchitectureItem, HistoryStep, JobItem, ModelItem, ResearchResult, SearchItem, Worker } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { useGo } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { formatBytes, formatCompact, Loaded, PageHeader, Panel, shortId, Sparkline, Status, statusTone, Unavailable } from "../studio/ui"

export const SUITE = "nasbench201_cifar10_full_suite"
type Session = SearchItem & { job?: JobItem & { payload?: Record<string, unknown> } }
type Workers = { configured: boolean; status: string; workers: Worker[] }
type Queue = { backend: string; available: boolean; queued?: number; running?: number; terminal?: number; error?: string }

function bestSoFar(history: HistoryStep[]): number[] {
  let best = Number.NEGATIVE_INFINITY
  return history.map((step) => (best = Math.max(best, step.validation_accuracy)))
}

export function Overview() {
  const go = useGo()
  const architectures = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures", 15_000, itemsResponse)
  const searches = usePoll<{ items: Session[] }>("/v1/searches", 10_000, itemsResponse)
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs", 8_000, itemsResponse)
  const models = usePoll<{ items: ModelItem[] }>("/v1/models", 30_000, itemsResponse)
  const workers = usePoll<Workers>("/v1/infrastructure/workers", 10_000)
  const queue = usePoll<Queue>("/v1/infrastructure/queue", 10_000)
  const suite = usePoll<ResearchResult>(`/v1/research/results/${SUITE}`, 0)

  const sessions = items(searches.data)
  const latestHistory = sessions.map((session) => jobResult<{ history?: HistoryStep[] }>(session.job)?.history ?? []).find((history) => history.length > 1) ?? []
  const policies = suite.data?.report ? splitAblations(suite.data).policies : []
  const bestPolicy = policies[0]
  const bestSummary = bestPolicy ? suite.data?.report?.algorithms[bestPolicy]?.best_validation_accuracy : undefined
  const recentJobs = [...items(jobs.data)].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")).slice(0, 6)
  const count = (poll: { data: { items?: unknown[] } | null; error: string | null; loaded: boolean }) => !poll.loaded ? "…" : poll.error ? "—" : String(items(poll.data).length)
  const modelsVerified = items(models.data).filter((model) => model.integrity_verified).length

  const cards: { label: string; value: string; sub: string; series: number[] }[] = [
    { label: "ARCHITECTURES", value: count(architectures), sub: "hash-addressed · validated", series: items(architectures.data).map((item) => item.metrics.parameters).reverse() },
    { label: "SEARCH SESSIONS", value: count(searches), sub: `${sessions.filter((session) => session.status === "running").length} running · ${sessions.filter((session) => session.status === "queued").length} queued`, series: bestSoFar(latestHistory) },
    { label: "BEST MEASURED VAL. ACC", value: bestSummary ? `${bestSummary.mean.toFixed(2)}%` : suite.error ? "—" : "…", sub: bestPolicy ? `${bestPolicy} · ${bestSummary?.n_seeds ?? "?"} seeds · benchmark_lookup` : "measured suite unavailable", series: policies.map((name) => suite.data!.report!.algorithms[name].best_validation_accuracy.mean).reverse() },
    { label: "CHECKPOINTS", value: count(models), sub: models.data ? `${modelsVerified} integrity-verified` : "registry", series: [] },
  ]

  return <div className="page">
    <PageHeader eyebrow="RESEARCH / COMMAND CENTER" title="Research overview" description="Live state of searches, jobs, registered architectures and measured results from the ArchAI API.">
      <button className="button" onClick={() => go("experiments")}><Icon name="experiments" /> View experiments</button>
      <button className="button primary" onClick={() => go("generator")}><Icon name="generator" /> Generate architecture</button>
    </PageHeader>
    <div className="metric-grid">
      {cards.map((card) => <div className="metric-card" key={card.label}>
        <div className="metric-label">{card.label}</div><div className="metric-value">{card.value}</div>
        <div className="metric-bottom"><span>{card.sub}</span><Sparkline values={card.series} /></div>
      </div>)}
    </div>
    <div className="overview-grid">
      <Panel title="Active research runs" meta={`${recentJobs.length} RECENT JOBS`} className="span-2">
        <Loaded poll={jobs} label="jobs" isEmpty={() => recentJobs.length === 0} empty="No jobs recorded yet. Launch a search or a training job.">{() => <div className="run-list">
          {recentJobs.map((job) => {
            const progress = jobProgress(job)
            const percent = progress ? Math.round(progressFraction(progress) * 100) : job.status === "succeeded" ? 100 : 0
            return <button className="run-row" key={job.job_id} onClick={() => go("experiments", { job: job.job_id })}>
              <span className="mono strong">{shortId(job.job_id, 8)}</span>
              <span><b>{job.kind}{typeof job.payload?.algorithm === "string" ? ` · ${job.payload.algorithm}` : ""}</b><small>{job.created_at ?? "created —"}</small></span>
              <span className="progress-cell"><span><i style={{ width: `${percent}%` }} /></span><small>{progress ? progressLabel(progress) : job.status}</small></span>
              <Status tone={statusTone(job.status)}>{job.status.toUpperCase()}</Status><Icon name="chevron" />
            </button>
          })}
        </div>}</Loaded>
      </Panel>
      <Panel title="Compute fabric" meta={workers.data ? `${workers.data.workers.length} WORKERS` : "WORKERS"}>
        <Loaded poll={workers} label="workers">{(data) => !data.configured
          ? <Unavailable feature="durable worker" reason="Redis is not configured on the API host; jobs run in-process only." />
          : data.workers.length === 0 ? <div className="empty-inline">No worker has reported a heartbeat.</div>
          : <div className="compute-list">{data.workers.map((worker) => <div className="compute-row" key={worker.worker_id}>
            <span className="gpu-icon"><Icon name="gpu" /></span><span><b>{worker.hostname}</b><small>{shortId(worker.worker_id, 8)} · seen {worker.last_seen}</small></span>
            <span className="util"><b>{worker.status.toUpperCase()}</b><small>{worker.active_job_id ? `job ${shortId(worker.active_job_id, 8)}` : "idle"}</small></span><i className={worker.active_job_id ? "" : "idle"} />
          </div>)}</div>}</Loaded>
        {queue.data && (queue.data.available
          ? <div className="queue-strip" aria-label={`Queue backend ${queue.data.backend}`}><span><small>QUEUED</small><b>{queue.data.queued ?? 0}</b></span><span><small>RUNNING</small><b>{queue.data.running ?? 0}</b></span><span><small>FINISHED</small><b>{queue.data.terminal ?? 0}</b></span></div>
          : <Unavailable feature="job queue" reason={`${queue.data.backend}: ${queue.data.error ?? "not configured"}`} />)}
        <p className="panel-note">GPU utilisation is not reported by the API; workers run CPU-scale jobs.</p>
      </Panel>
      <Panel title="Registered architectures" meta="ANALYTICAL METRICS" className="span-2">
        <Loaded poll={architectures} label="architectures" isEmpty={(data) => data.items.length === 0} empty="No architectures registered. Validate and register one in the Architecture Explorer.">
          {(data) => <div className="table-wrap"><table><thead><tr><th>ARCH ID</th><th>SEARCH SPACE</th><th>PARAMS</th><th>FLOPs</th><th>ACT. MEMORY</th><th>EVIDENCE</th></tr></thead>
            <tbody>{data.items.slice(0, 8).map((item) => <tr key={item.architecture_id} onClick={() => go("explorer", { id: item.architecture_id })} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && go("explorer", { id: item.architecture_id })}>
              <td className="mono accent">{shortId(item.architecture_id)}</td><td>{item.search_space}</td><td className="mono">{formatCompact(item.metrics.parameters)}</td><td className="mono">{formatCompact(item.metrics.flops)}</td><td className="mono">{formatBytes(item.metrics.activation_memory_bytes)}</td><td><span className="badge badge-candidate">ANALYTICAL</span></td>
            </tr>)}</tbody></table></div>}
        </Loaded>
      </Panel>
      <Panel title="Research activity" meta="RECENT JOB EVENTS">
        <Loaded poll={jobs} label="activity" isEmpty={() => recentJobs.length === 0} empty="No activity recorded.">{() => <div className="activity-list">
          {recentJobs.map((job) => <div className="activity" key={job.job_id}><time>{(job.created_at ?? "").slice(11, 19) || "—"}</time><i className={`dot-${statusTone(job.status)}`} /><span>{job.kind} {shortId(job.job_id, 8)} {job.status}{job.error ? ` — ${job.error}` : ""}</span></div>)}
        </div>}</Loaded>
      </Panel>
      <ProjectPicker />
      <Panel title="Measured benchmark" meta="BEST VAL. ACC @ 100 QUERIES">
        <Loaded poll={suite} label="measured suite" isEmpty={(data) => !data.report} empty="This result set has no report.">{(data) => <div className="table-wrap"><table><thead><tr><th>POLICY</th><th>MEAN [95% CI]</th></tr></thead><tbody>
          {splitAblations(data).policies.map((name) => <tr key={name}><td>{name}</td><td className="mono">{ci(data.report!.algorithms[name].best_validation_accuracy)}</td></tr>)}
        </tbody></table></div>}</Loaded>
        <button className="button full" onClick={() => go("benchmarks")}>All measured results <Icon name="chevron" /></button>
      </Panel>
    </div>
    <div className="data-notice">Architecture metrics are analytical (computed from the graph). Accuracy figures are measured NATS-Bench lookups (evidence: benchmark_lookup). Nothing on this screen is illustrative.</div>
  </div>
}
