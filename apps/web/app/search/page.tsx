"use client"
import { useState } from "react"
import { Empty, Errors, Loaded, PageHeader, Unavailable } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { postJson } from "../lib/api"
import { buildSearchRequest, defaultSearchForm, type SearchForm } from "../lib/forms"
import { jobResult } from "../lib/results"
import type { HistoryStep, JobDetail, SearchAlgorithm, SearchItem } from "../lib/types"

type Session = SearchItem & { job?: JobDetail }

export default function AutonomousSearchLaboratory() {
  const [form, setForm] = useState<SearchForm>(defaultSearchForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const algorithms = usePoll<{ items: SearchAlgorithm[] }>("/v1/search/algorithms", 0)
  const searches = usePoll<{ items: Session[] }>("/v1/searches")
  const selected = usePoll<Session>(selectedId ? `/v1/searches/${selectedId}` : null, 4000)
  const chosen = items(algorithms.data).find((item) => item.name === form.algorithm)
  const update = (field: keyof SearchForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildSearchRequest(form)
    if (!built.ok) { setErrors(built.errors); return }
    if (chosen && !chosen.available) { setErrors([`${chosen.label} is unavailable: ${chosen.unavailable_reason}`]); return }
    setErrors([])
    const created = await postJson<SearchItem>("/v1/searches", built.value)
    if (!created.ok) { setErrors([`${created.status}: ${created.detail}`]); return }
    const started = await postJson(`/v1/searches/${created.data.search_id}/start`, {})
    setMessage(started.ok ? `Queued search ${created.data.search_id.slice(0, 8)} for the durable worker.` : `Search ${created.data.search_id.slice(0, 8)} recorded; start failed (${started.status}: ${started.detail}).`)
    setSelectedId(created.data.search_id)
    searches.refresh()
  }
  const cancel = async (id: string) => {
    const outcome = await postJson(`/v1/searches/${id}/cancel`, {})
    if (!outcome.ok) setErrors([`${outcome.status}: ${outcome.detail}`])
    searches.refresh(); selected.refresh()
  }
  const result = jobResult<Record<string, unknown> & { history?: HistoryStep[] }>(selected.data?.job)
  return <>
    <PageHeader eyebrow="AUTONOMOUS SEARCH LABORATORY" title="Budgeted architecture search" note="Searches run on the Redis worker against the checksum-verified NATS-Bench archive (evidence: benchmark_lookup). Selection uses validation accuracy only; test accuracy is reported for the selected cell." />
    <div className="grid">
      <article className="panel"><h3>New search</h3>
        <div className="form">
          <Loaded poll={algorithms}>{(data) => <label>Policy<select value={form.algorithm} onChange={update("algorithm")}>
            {items(data).map((item) => <option key={item.name} value={item.name} disabled={!item.available}>{item.label}{item.available ? "" : " — unavailable"}</option>)}</select></label>}</Loaded>
          {chosen ? <p className="muted">{chosen.description}{chosen.parameters.length ? ` Tunable via the API params object: ${chosen.parameters.join(", ")} (Studio submits registry defaults).` : ""}</p> : null}
          {chosen && !chosen.available ? <Unavailable feature={chosen.label} reason={chosen.unavailable_reason ?? "not installed on this API host"} /> : null}
          <label>Dataset<input value={form.datasetId} onChange={update("datasetId")} /></label>
          <label>Budget (benchmark queries)<input inputMode="numeric" value={form.budget} onChange={update("budget")} /></label>
          <label>Seed<input inputMode="numeric" value={form.seed} onChange={update("seed")} /></label>
          <label>Search-space indices (e.g. 0:256 or 1,5,9)<input value={form.indices} onChange={update("indices")} /></label>
          <button onClick={() => void submit()}>Launch search</button>
        </div>
        <Errors errors={errors} />{message ? <p className="muted" role="status">{message}</p> : null}
      </article>
      <article className="panel"><h3>Sessions</h3>
        <Loaded poll={searches} isEmpty={(data) => items(data).length === 0} empty="No search sessions recorded.">{(data) => <ul>{items(data).map((item) => <li key={item.search_id}>
          <button className="link-button" onClick={() => setSelectedId(item.search_id)}><code>{item.algorithm} · seed {item.seed} · {item.search_id.slice(0, 8)}</code></button>
          <span className={`job-${item.status}`}>{item.status}{item.status === "queued" || item.status === "running" ? <> · <button className="link-button" onClick={() => void cancel(item.search_id)}>cancel</button></> : null}</span></li>)}</ul>}</Loaded>
      </article>
      <article className="panel wide"><h3>Session detail</h3>
        {!selectedId ? <Empty>Select a session to see its per-step history.</Empty> : <Loaded poll={selected}>{(session) => <>
          <p className="muted">{session.algorithm} · {session.status}{session.job?.error ? ` · error: ${session.job.error}` : ""}</p>
          {result ? <>
            <div className="table-scroll"><table><tbody>
              <tr><th>Selected cell</th><td><code>{String(result.selected_architecture_string ?? result.selected_index)}</code></td></tr>
              <tr><th>Best validation accuracy (selection)</th><td className="num">{Number(result.selected_validation_accuracy).toFixed(2)}%</td></tr>
              <tr><th>Held-out test accuracy of selected cell</th><td className="num">{Number(result.held_out_test_accuracy).toFixed(2)}%</td></tr>
              <tr><th>Queries / evaluations</th><td className="num">{String(result.queries)} / {String(result.evaluations)}</td></tr>
              {typeof result.hypervolume_validation_params === "number" ? <tr><th>Hypervolume (val %, params M; ref 0, 1.6)</th><td className="num">{result.hypervolume_validation_params.toFixed(2)}</td></tr> : null}
              <tr><th>Evidence</th><td>{String(result.evidence_type)}</td></tr>
            </tbody></table></div>
            <div className="table-scroll"><table><thead><tr><th>Step</th><th>Index</th><th>Validation %</th><th>Params (M)</th><th>Best so far</th></tr></thead><tbody>
              {(result.history ?? []).reduce<{ rows: React.ReactNode[]; best: number }>((acc, step) => {
                const best = Math.max(acc.best, step.validation_accuracy)
                acc.rows.push(<tr key={step.step}><td className="num">{step.step}</td><td className="num">{step.index}</td><td className="num">{step.validation_accuracy.toFixed(2)}</td><td className="num">{step.params_m?.toFixed(3) ?? "—"}</td><td className="num">{best.toFixed(2)}</td></tr>)
                return { rows: acc.rows, best }
              }, { rows: [], best: Number.NEGATIVE_INFINITY }).rows}
            </tbody></table></div>
          </> : <Empty>No result yet (status: {session.status}).</Empty>}
        </>}</Loaded>}
      </article>
    </div>
  </>
}
