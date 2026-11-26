"use client"
import { useState } from "react"
import { Empty, Errors, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { postJson } from "../lib/api"
import { buildSearchRequest, defaultSearchForm, SEARCH_ALGORITHMS, type SearchForm } from "../lib/forms"
import type { JobItem, SearchItem } from "../lib/types"

export default function SearchLab() {
  const [form, setForm] = useState<SearchForm>(defaultSearchForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const searches = usePoll<{ items: SearchItem[] }>("/v1/searches")
  const jobs = items(usePoll<{ items: JobItem[] }>("/v1/jobs").data)
  const status = (id: string) => jobs.find((job) => job.job_id === id)?.status ?? "unknown"
  const update = (field: keyof SearchForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildSearchRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    setErrors([])
    const created = await postJson<SearchItem>("/v1/searches", built.value)
    if (!created.ok) { setErrors([`${created.status}: ${created.detail}`]); return }
    const started = await postJson(`/v1/searches/${created.data.search_id}/start`, {})
    setMessage(started.ok ? `Queued search ${created.data.search_id.slice(0, 8)} for the durable worker.` : `Search ${created.data.search_id.slice(0, 8)} recorded; start failed (${started.status}: ${started.detail}).`)
    searches.refresh()
  }
  return <>
    <PageHeader eyebrow="SEARCH LABORATORY" title="Launch a budgeted search" note="Benchmark searches run on the Redis worker against the checksum-verified NATS-Bench archive. Selection uses validation accuracy only." />
    <div className="grid">
      <article className="panel">
        <h3>New search</h3>
        <div className="form">
          <label>Algorithm<select value={form.algorithm} onChange={update("algorithm")}>{SEARCH_ALGORITHMS.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label>Dataset<input value={form.datasetId} onChange={update("datasetId")} /></label>
          <label>Budget (benchmark queries)<input value={form.budget} onChange={update("budget")} /></label>
          <label>Seed<input value={form.seed} onChange={update("seed")} /></label>
          <label>Indices (e.g. 0:256 or 1,5,9)<input value={form.indices} onChange={update("indices")} /></label>
          <button onClick={() => void submit()}>Launch search</button>
        </div>
        <Errors errors={errors} />{message ? <p className="muted" role="status">{message}</p> : null}
      </article>
      <article className="panel"><h3>Sessions</h3>{items(searches.data).length === 0 ? <Empty>No search sessions recorded.</Empty> : <ul>{items(searches.data).map((item) => <li key={item.search_id}><code>{item.algorithm} · seed {item.seed}</code><span className={`job-${status(item.search_id)}`}>{status(item.search_id)}</span></li>)}</ul>}</article>
    </div>
  </>
}
