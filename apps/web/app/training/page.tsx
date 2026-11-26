"use client"
import { useState } from "react"
import { Empty, Errors, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { postJson } from "../lib/api"
import { buildTrainingRequest, defaultTrainingForm, type TrainingForm, type TrainingKind } from "../lib/forms"
import type { JobItem } from "../lib/types"

export default function Training() {
  const [form, setForm] = useState<TrainingForm>(defaultTrainingForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs")
  const update = (field: keyof TrainingForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildTrainingRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    setErrors([])
    const created = await postJson<JobItem>("/v1/training", built.value)
    if (created.ok) { setMessage(`Queued ${created.data.kind} job ${created.data.job_id.slice(0, 8)}.`); jobs.refresh() } else setErrors([`${created.status}: ${created.detail}`])
  }
  const cancel = async (jobId: string) => { await postJson(`/v1/jobs/${jobId}/cancel`, {}); jobs.refresh() }
  return <>
    <PageHeader eyebrow="TRAINING JOBS" title="Queue training on the durable worker" note="Candidate jobs use synthetic smoke-scale data only; predictor jobs need the checksum-verified benchmark archive." />
    <div className="grid">
      <article className="panel"><h3>New job</h3>
        <div className="form">
          <label>Kind<select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as TrainingKind })}><option>candidate</option><option>generator</option><option>predictor</option></select></label>
          <label>Epochs<input value={form.epochs} onChange={update("epochs")} /></label>
          <label>Seed<input value={form.seed} onChange={update("seed")} /></label>
          <label>Checkpoint path<input value={form.checkpointPath} onChange={update("checkpointPath")} /></label>
          {form.kind === "candidate" ? <label>Architecture JSON<textarea rows={5} value={form.architectureJson} onChange={update("architectureJson")} /></label> : null}
          {form.kind === "generator" ? <label>Corpus path (JSONL)<input value={form.corpusPath} onChange={update("corpusPath")} /></label> : null}
          {form.kind === "predictor" ? <><label>Benchmark path<input value={form.benchmarkPath} onChange={update("benchmarkPath")} /></label><label>Benchmark SHA-256<input value={form.benchmarkSha256} onChange={update("benchmarkSha256")} /></label><label>Indices<input value={form.indices} onChange={update("indices")} /></label></> : null}
          <button onClick={() => void submit()}>Queue job</button>
        </div>
        <Errors errors={errors} />{message ? <p className="muted" role="status">{message}</p> : null}
      </article>
      <article className="panel"><h3>Jobs</h3>{items(jobs.data).length === 0 ? <Empty>No jobs recorded.</Empty> : <ul>{items(jobs.data).map((job) => <li key={job.job_id}><code>{job.kind} · {job.job_id.slice(0, 8)}</code><span className={`job-${job.status}`}>{job.status}{job.status === "queued" || job.status === "running" ? <> · <button className="link-button" onClick={() => void cancel(job.job_id)}>cancel</button></> : null}</span></li>)}</ul>}</article>
    </div>
  </>
}
