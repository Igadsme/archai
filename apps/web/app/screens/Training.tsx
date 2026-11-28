"use client"
import { useEffect, useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { describeFailure, downloadJson, postJson } from "../lib/api"
import { buildTrainingRequest, defaultTrainingForm, type TrainingForm, type TrainingKind } from "../lib/forms"
import { jobProgress, progressFraction } from "../lib/progress"
import { jobResult } from "../lib/results"
import type { JobDetail, JobItem, Worker } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { LineChart } from "../studio/charts"
import { useQueryParam } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { GpuTelemetryView, useTelemetry } from "../studio/Telemetry"
import { EmptyState, ErrorList, Loaded, Notice, PageHeader, Panel, shortId, Status, statusTone } from "../studio/ui"

export const TRAINING_KINDS = new Set(["training", "generator_training", "predictor_training"])
const COLORS = ["#5fc8c1", "#7ba4e8", "#d3a85f", "#df7b78", "#8fc39d"]

/** Measured curve rows from a finished result or live worker progress; never interpolated. */
export function trainingCurve(job: JobDetail | null | undefined): Record<string, number>[] {
  const result = jobResult(job)
  const progress = jobProgress(job)
  const raw = Array.isArray(result?.training_loss) ? result.training_loss as unknown[] : Array.isArray(result?.history) ? result.history as unknown[] : progress?.phase === "training" ? progress.history : []
  return raw.map((row, index): Record<string, number> => typeof row === "number" ? { epoch: index + 1, training_loss: row }
    : row && typeof row === "object" ? { epoch: index + 1, ...Object.fromEntries(Object.entries(row as Record<string, unknown>).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]))) } : { epoch: index + 1 })
}

export const TERMINAL = new Set(["succeeded", "failed", "cancelled"])

function clock(seconds: number): string {
  seconds = Math.max(0, Math.round(seconds))
  return `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`
}

export function Training() {
  const requested = useQueryParam("job")
  const [form, setForm] = useState<TrainingForm>(defaultTrainingForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [metric, setMetric] = useState<string | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs", 5_000, itemsResponse)
  const detail = usePoll<JobDetail>(jobId ? `/v1/jobs/${encodeURIComponent(jobId)}` : null, 3_000)
  const workers = usePoll<{ configured: boolean; workers: Worker[] }>("/v1/infrastructure/workers", 10_000)
  const telemetry = useTelemetry(10_000)
  const training = items(jobs.data).filter((job) => TRAINING_KINDS.has(job.kind))
  useEffect(() => { if (requested) setJobId(requested) }, [requested])
  useEffect(() => { if (!jobId && !requested && training[0]) setJobId(training[0].job_id) }, [jobId, requested, training])
  const update = (field: keyof TrainingForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildTrainingRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    setErrors([]); setBusy(true)
    const created = await postJson<JobItem>("/v1/training", built.value)
    setBusy(false)
    if (created.ok) { setMessage(`Queued ${created.data.kind} job ${created.data.job_id.slice(0, 8)}.`); setJobId(created.data.job_id); jobs.refresh() } else setErrors([describeFailure(created)])
  }
  const cancel = async (id: string) => {
    const outcome = await postJson(`/v1/jobs/${id}/cancel`, {})
    if (!outcome.ok) setErrors([describeFailure(outcome)])
    else setMessage(`Cancellation requested for ${id.slice(0, 8)}.`)
    jobs.refresh(); detail.refresh()
  }

  const job = detail.data
  const result = jobResult(job)
  const progress = jobProgress(job)
  const curve = trainingCurve(job)
  const keys = Array.from(new Set(curve.flatMap((row) => Object.keys(row)))).filter((key) => key !== "epoch")
  const activeMetric = metric && keys.includes(metric) ? metric : keys[0] ?? null
  const last = curve[curve.length - 1]
  const epochs = progress?.phase === "training" ? `${progress.epochs_completed} / ${progress.epochs}` : curve.length ? `${curve.length} / ${String(job?.payload?.epochs ?? curve.length)}` : "—"
  const percent = progress ? `${Math.round(progressFraction(progress) * 100)}%` : job?.status === "succeeded" ? "100%" : "—"
  const stats: [string, string, string][] = [
    ["EPOCH", epochs, percent],
    [`LAST ${(keys[0] ?? "LOSS").toUpperCase().replaceAll("_", " ")}`, last && keys[0] ? last[keys[0]].toFixed(4) : "—", "measured"],
    [keys[1] ? `LAST ${keys[1].toUpperCase().replaceAll("_", " ")}` : "SECOND METRIC", last && keys[1] ? last[keys[1]].toFixed(4) : "—", keys[1] ? "measured" : "not reported"],
    ["STATUS", job ? job.status.toUpperCase() : "—", job?.kind ?? ""],
    typeof result?.wall_clock_seconds === "number" ? ["WALL CLOCK", result.wall_clock_seconds < 60 ? `${result.wall_clock_seconds.toFixed(2)} s` : clock(result.wall_clock_seconds), "measured by the worker"]
      : ["LAST UPDATE", job?.updated_at?.slice(11, 19) ?? "—", job && !TERMINAL.has(job.status) && job.created_at ? `${clock((Date.now() - Date.parse(job.created_at)) / 1000)} since queued` : job?.status ?? ""],
  ]
  const events = job ? ([["CREATED", job.created_at, `${job.kind} queued`], ["PROGRESS", progress?.reported_at, progress?.phase === "training" ? `epoch ${progress.epochs_completed} of ${progress.epochs}` : undefined], [TERMINAL.has(job.status) ? job.status.toUpperCase() : "UPDATED", job.updated_at, job.error ? `failed: ${job.error}` : `status ${job.status}`]] as [string, string | null | undefined, string | undefined][]).filter((event) => event[1]) : []

  return <div className="page">
    <PageHeader eyebrow={`TRAINING${job ? ` / ${shortId(job.job_id, 8).toUpperCase()}` : ""}`} title="Training & GPU monitoring" description="Smoke-scale training on the durable worker. GPU readings are live from NVML or torch.cuda when a GPU is visible. Candidate jobs use synthetic data (evidence: synthetic_training); generator and predictor jobs need checksum-verified benchmark data.">
      {job ? <Status tone={statusTone(job.status)}>{job.status.toUpperCase()}{progress?.phase === "training" ? ` · EPOCH ${progress.epochs_completed}` : ""}</Status> : null}
      <button className="button" disabled={!job} onClick={() => setShowConfig((value) => !value)}>Inspect configuration</button>
      <button className="button" disabled={!job} onClick={() => job && downloadJson(`archai-job-${job.job_id.slice(0, 8)}.json`, { exported_at: new Date().toISOString(), evidence: "API job record as returned by GET /v1/jobs/{id}", job })}><Icon name="download" /> Export job JSON</button>
    </PageHeader>
    {showConfig && job && <div className="training-config-banner"><span>RUN CONFIGURATION</span><code>{Object.entries(job.payload ?? {}).filter(([key]) => key !== "result" && key !== "progress" && key !== "architecture").map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ") || "no payload"}</code><button aria-label="Close configuration" onClick={() => setShowConfig(false)}><Icon name="close" /></button></div>}
    <div className="training-stats">{stats.map((stat) => <div key={stat[0]}><span>{stat[0]}</span><b>{stat[1]}</b><small>{stat[2]}</small></div>)}</div>
    <div className="training-grid">
      <Panel title="Training jobs" meta={`${training.length} RECORDED`} className="span-2">
        <Loaded poll={jobs} label="jobs" isEmpty={() => training.length === 0} empty="No training jobs recorded. Queue one with the form on the right.">{() => <div className="experiment-list session-list">
          {training.map((item) => <div key={item.job_id} className={`job-row ${item.job_id === jobId ? "active" : ""}`}>
            <button className="job-select" onClick={() => setJobId(item.job_id)} aria-pressed={item.job_id === jobId}><span><b className="mono">{item.kind} · {item.job_id.slice(0, 8)}</b><small>{item.created_at ?? ""}</small></span></button>
            <Status tone={statusTone(item.status)}>{item.status.toUpperCase()}</Status>
            {item.status === "queued" || item.status === "running" ? <button className="button compact" onClick={() => void cancel(item.job_id)}>Cancel</button> : <span />}
          </div>)}
        </div>}</Loaded>
      </Panel>
      <Panel title="New job" meta="POST /v1/training">
        <div className="form-body stacked-form">
          <label className="field"><span>Kind</span><select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as TrainingKind })}><option value="candidate">candidate (synthetic smoke)</option><option value="generator">ArchAI-V1 generator</option><option value="predictor">ArchAI-V1 predictor</option></select></label>
          <div className="form-grid">
            <label className="field"><span>Epochs</span><input inputMode="numeric" value={form.epochs} onChange={update("epochs")} /></label>
            <label className="field"><span>Seed</span><input inputMode="numeric" value={form.seed} onChange={update("seed")} /></label>
          </div>
          <label className="field"><span>Checkpoint path <em>UNDER ALLOWED DATA ROOT</em></span><input value={form.checkpointPath} onChange={update("checkpointPath")} placeholder={form.kind === "candidate" ? "empty: the worker's ARCHAI_CHECKPOINT_DIR, if set" : "/absolute/path.pt"} /></label>
          {form.kind === "candidate" ? <label className="field"><span>Architecture JSON</span><textarea rows={4} value={form.architectureJson} onChange={update("architectureJson")} /></label> : null}
          {form.kind === "generator" ? <label className="field"><span>Corpus path (JSONL)</span><input value={form.corpusPath} onChange={update("corpusPath")} /></label> : null}
          {form.kind === "predictor" ? <><label className="field"><span>Benchmark path</span><input value={form.benchmarkPath} onChange={update("benchmarkPath")} /></label><label className="field"><span>Benchmark SHA-256</span><input value={form.benchmarkSha256} onChange={update("benchmarkSha256")} /></label><label className="field"><span>Indices</span><input value={form.indices} onChange={update("indices")} /></label></> : null}
          <button className="button primary" onClick={() => void submit()} disabled={busy}><Icon name="play" /> {busy ? "Queueing…" : "Queue job"}</button>
          <ErrorList errors={errors} /><Notice>{message}</Notice>
        </div>
      </Panel>
      <Panel title="Optimization curves" meta={curve.length ? `${curve.length} EPOCHS · MEASURED` : "NO CURVE"} className="span-2"
        actions={keys.length ? <div className="segmented" role="group" aria-label="Curve metric">{keys.map((key) => <button key={key} aria-pressed={activeMetric === key} className={activeMetric === key ? "active" : ""} onClick={() => setMetric(key)}>{key.toUpperCase().replaceAll("_", " ")}</button>)}</div> : undefined}>
        {activeMetric && curve.filter((row) => typeof row[activeMetric] === "number").length > 1
          ? <LineChart label={`${activeMetric} per epoch`} xLabel="epochs" yFormat={(value) => value.toFixed(3)} series={[{ label: `${activeMetric} (measured)`, variant: "main", area: true, color: COLORS[keys.indexOf(activeMetric) % COLORS.length], points: curve.filter((row) => typeof row[activeMetric] === "number").map((row) => ({ x: row.epoch, y: row[activeMetric] })) }]} />
          : <EmptyState icon="training" title={job ? (curve.length === 1 ? "One epoch recorded" : "No curve reported yet") : "No job selected"}>{job ? <p>{job.kind === "training" ? "Candidate jobs report per-epoch loss while running." : "Generator and predictor jobs report their loss curve when they finish."}</p> : null}</EmptyState>}
        {curve.length ? <div className="table-wrap curve-table"><table aria-label="Measured training curve"><thead><tr><th>EPOCH</th>{keys.map((key) => <th key={key}>{key} (measured)</th>)}</tr></thead><tbody>{curve.map((row) => <tr key={row.epoch}><td className="mono">{row.epoch}</td>{keys.map((key) => <td className="mono" key={key}>{typeof row[key] === "number" ? row[key].toFixed(4) : "—"}</td>)}</tr>)}</tbody></table></div> : null}
      </Panel>
      <Panel title="GPU telemetry" meta="/v1/infrastructure/telemetry">
        <GpuTelemetryView poll={telemetry} />
        <Loaded poll={workers} label="workers">{(data) => <div className="worker-list">{!data.configured ? <div><i className="queued" /><code>redis</code><span>not configured</span><b>—</b></div> : data.workers.length ? data.workers.map((worker) => <div key={worker.worker_id}><i className={worker.active_job_id ? "" : "queued"} /><code>{worker.hostname.slice(0, 10)}</code><span>{worker.active_job_id ? `job ${shortId(worker.active_job_id, 8)}` : "idle"}</span><b>{worker.status}</b></div>) : <div><i className="queued" /><code>—</code><span>no heartbeat</span><b>—</b></div>}</div>}</Loaded>
      </Panel>
      <Panel title="Training events" meta="JOB TIMELINE" className="span-2">
        {events.length ? <div className="event-table">{events.map(([kind, at, text]) => <div key={kind}><time>{(at ?? "").slice(11, 19)}</time><b>{kind}</b><span>{text}</span><code>{at}</code></div>)}</div> : <div className="empty-inline">Select a job to see its timeline.</div>}
        {job?.error ? <div className="error-state"><div><span>!</span><h3>Job failed</h3></div><pre>{job.error}</pre></div> : null}
      </Panel>
      <Panel title="Job result" meta={result ? "PAYLOAD.RESULT" : "PENDING"}>
        {result ? <pre className="result-json">{JSON.stringify({ ...result, training_loss: undefined, history: undefined }, null, 1)}</pre> : <div className="empty-inline">No result yet{job ? ` (status: ${job.status})` : ""}.</div>}
      </Panel>
    </div>
  </div>
}
