"use client"
import { useState } from "react"
import { Empty, Errors, Loaded, PageHeader, Unavailable } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { postJson } from "../lib/api"
import { buildTrainingRequest, defaultTrainingForm, type TrainingForm, type TrainingKind } from "../lib/forms"
import { jobResult } from "../lib/results"
import type { JobDetail, JobItem } from "../lib/types"

const TRAINING_KINDS = new Set(["training", "generator_training", "predictor_training"])

export default function TrainingLaboratory() {
  const [form, setForm] = useState<TrainingForm>(defaultTrainingForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs")
  const detail = usePoll<JobDetail>(jobId ? `/v1/jobs/${jobId}` : null, 4000)
  const training = items(jobs.data).filter((job) => TRAINING_KINDS.has(job.kind))
  const update = (field: keyof TrainingForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildTrainingRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    setErrors([])
    const created = await postJson<JobItem>("/v1/training", built.value)
    if (created.ok) { setMessage(`Queued ${created.data.kind} job ${created.data.job_id.slice(0, 8)}.`); setJobId(created.data.job_id); jobs.refresh() } else setErrors([`${created.status}: ${created.detail}`])
  }
  const cancel = async (id: string) => {
    const outcome = await postJson(`/v1/jobs/${id}/cancel`, {})
    if (!outcome.ok) setErrors([`${outcome.status}: ${outcome.detail}`])
    jobs.refresh(); detail.refresh()
  }
  const result = jobResult(detail.data)
  const rawCurve = Array.isArray(result?.training_loss) ? result?.training_loss as unknown[] : Array.isArray(result?.history) ? result?.history as unknown[] : []
  const curve: Record<string, number>[] = rawCurve.map((row) => typeof row === "number" ? { training_loss: row } : (row && typeof row === "object" ? row as Record<string, number> : {}))
  const curveKeys = Array.from(new Set(curve.flatMap((row) => Object.keys(row)))).filter((key) => key !== "epoch")
  return <>
    <PageHeader eyebrow="TRAINING LABORATORY" title="Smoke-scale training on the durable worker" note="CPU-small only. Candidate jobs use synthetic data (evidence: synthetic_training); generator/predictor jobs need checksum-verified benchmark data. No GPU or paid compute is used." />
    <div className="grid">
      <article className="panel"><h3>New job</h3>
        <div className="form">
          <label>Kind<select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as TrainingKind })}><option value="candidate">candidate (synthetic smoke)</option><option value="generator">ArchAI-V1 generator</option><option value="predictor">ArchAI-V1 predictor</option></select></label>
          <label>Epochs<input inputMode="numeric" value={form.epochs} onChange={update("epochs")} /></label>
          <label>Seed<input inputMode="numeric" value={form.seed} onChange={update("seed")} /></label>
          <label>Checkpoint path (must be under the allowed data root)<input value={form.checkpointPath} onChange={update("checkpointPath")} /></label>
          {form.kind === "candidate" ? <label>Architecture JSON<textarea rows={5} value={form.architectureJson} onChange={update("architectureJson")} /></label> : null}
          {form.kind === "generator" ? <label>Corpus path (JSONL)<input value={form.corpusPath} onChange={update("corpusPath")} /></label> : null}
          {form.kind === "predictor" ? <><label>Benchmark path<input value={form.benchmarkPath} onChange={update("benchmarkPath")} /></label><label>Benchmark SHA-256<input value={form.benchmarkSha256} onChange={update("benchmarkSha256")} /></label><label>Indices<input value={form.indices} onChange={update("indices")} /></label></> : null}
          <button onClick={() => void submit()}>Queue job</button>
        </div>
        <Errors errors={errors} />{message ? <p className="muted" role="status">{message}</p> : null}
      </article>
      <article className="panel"><h3>Training jobs</h3>
        <Loaded poll={jobs} isEmpty={() => training.length === 0} empty="No training jobs recorded.">{() => <ul>{training.map((job) => <li key={job.job_id}>
          <button className="link-button" onClick={() => setJobId(job.job_id)}><code>{job.kind} · {job.job_id.slice(0, 8)}</code></button>
          <span className={`job-${job.status}`}>{job.status}{job.status === "queued" || job.status === "running" ? <> · <button className="link-button" onClick={() => void cancel(job.job_id)}>cancel</button></> : null}</span></li>)}</ul>}</Loaded>
      </article>
      <article className="panel wide"><h3>Job detail</h3>
        <Unavailable feature="live per-epoch progress" reason="The worker reports loss curves only when a job finishes; there is no streaming progress channel yet." />
        {!jobId ? <Empty>Select a job to see its result.</Empty> : <Loaded poll={detail}>{(job) => <>
          <p className="muted">{job.kind} · {job.status}{job.started_at ? ` · started ${job.started_at}` : ""}{job.finished_at ? ` · finished ${job.finished_at}` : ""}</p>
          {job.error ? <p className="errors" role="alert">{job.error}</p> : null}
          {curve.length ? <div className="table-scroll"><table><thead><tr><th>Epoch</th>{curveKeys.map((key) => <th key={key}>{key} (measured)</th>)}</tr></thead><tbody>{curve.map((row, index) => <tr key={index}><td className="num">{row.epoch ?? index + 1}</td>{curveKeys.map((key) => <td className="num" key={key}>{typeof row[key] === "number" ? row[key].toFixed(4) : "—"}</td>)}</tr>)}</tbody></table></div> : null}
          {result ? <pre className="readme">{JSON.stringify({ ...result, training_loss: undefined, history: undefined }, null, 1)}</pre> : <Empty>No result yet.</Empty>}
        </>}</Loaded>}
      </article>
    </div>
  </>
}
