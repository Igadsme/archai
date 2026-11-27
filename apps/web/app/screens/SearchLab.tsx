"use client"
import { useEffect, useState } from "react"
import { ConstraintFields } from "../components/ConstraintFields"
import { SelectedProjectLabel, useSelectedProject } from "../components/ProjectPicker"
import { items, usePoll } from "../components/usePoll"
import { describeFailure, postJson } from "../lib/api"
import { buildSearchRequest, defaultSearchForm, type SearchForm } from "../lib/forms"
import { jobProgress, progressFraction, progressLabel } from "../lib/progress"
import { jobResult } from "../lib/results"
import type { HistoryStep, JobDetail, SearchAlgorithm, SearchItem, Worker } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { LineChart } from "../studio/charts"
import { useGo, useQueryParam } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { EmptyState, ErrorList, Loaded, Notice, PageHeader, Panel, shortId, Status, statusTone, Unavailable } from "../studio/ui"

type Session = SearchItem & { job?: JobDetail; dataset_id: string }
type SearchResult = Record<string, unknown> & { history?: HistoryStep[] }

export function bestSoFarSeries(history: HistoryStep[]): { step: number; best: number }[] {
  let best = Number.NEGATIVE_INFINITY
  return history.map((step) => ({ step: step.step, best: (best = Math.max(best, step.validation_accuracy)) }))
}

export function SearchLab() {
  const go = useGo()
  const requested = useQueryParam("session")
  const { projectId } = useSelectedProject()
  const [form, setForm] = useState<SearchForm>(defaultSearchForm)
  const [errors, setErrors] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cell, setCell] = useState<number | null>(null)
  const algorithms = usePoll<{ items: SearchAlgorithm[] }>("/v1/search/algorithms", 0, itemsResponse)
  const searches = usePoll<{ items: Session[] }>("/v1/searches", 6_000, itemsResponse)
  const selected = usePoll<Session>(selectedId ? `/v1/searches/${encodeURIComponent(selectedId)}` : null, 3_000)
  const workers = usePoll<{ configured: boolean; workers: Worker[] }>("/v1/infrastructure/workers", 10_000)
  useEffect(() => { if (requested) setSelectedId(requested) }, [requested])
  useEffect(() => { if (!selectedId && !requested && searches.data?.items[0]) setSelectedId(searches.data.items[0].search_id) }, [requested, searches.data, selectedId])
  useEffect(() => setCell(null), [selectedId])

  const chosen = items(algorithms.data).find((item) => item.name === form.algorithm)
  const update = (field: keyof SearchForm) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value })
  const submit = async () => {
    const built = buildSearchRequest({ ...form, projectId: projectId || undefined })
    if (!built.ok) { setErrors(built.errors); return }
    if (chosen && !chosen.available) { setErrors([`${chosen.label} is unavailable: ${chosen.unavailable_reason}`]); return }
    setErrors([]); setBusy(true)
    const created = await postJson<SearchItem>("/v1/searches", built.value)
    if (!created.ok) { setBusy(false); setErrors([describeFailure(created)]); return }
    const started = await postJson(`/v1/searches/${created.data.search_id}/start`, {})
    setBusy(false)
    setMessage(started.ok ? `Queued search ${created.data.search_id.slice(0, 8)} for the durable worker.` : `Search ${created.data.search_id.slice(0, 8)} recorded; start failed (${describeFailure(started)}).`)
    setSelectedId(created.data.search_id)
    searches.refresh()
  }
  const cancel = async (id: string) => {
    const outcome = await postJson(`/v1/searches/${id}/cancel`, {})
    if (!outcome.ok) setErrors([describeFailure(outcome)])
    else setMessage(`Cancellation requested for ${id.slice(0, 8)}.`)
    searches.refresh(); selected.refresh()
  }

  const session = selected.data
  const result = jobResult<SearchResult>(session?.job)
  const history = result?.history ?? []
  const progress = jobProgress(session?.job)
  const budget = session?.budget_evaluations ?? (progress?.phase === "searching" ? progress.budget : undefined)
  const done = progress ? progressFraction(progress) : session?.status === "succeeded" ? 1 : 0
  const best = bestSoFarSeries(history)
  const bestIndex = history.length ? history.reduce((acc, step, index) => step.validation_accuracy > history[acc].validation_accuracy ? index : acc, 0) : -1
  const accuracies = history.map((step) => step.validation_accuracy)
  const [lo, hi] = accuracies.length ? [Math.min(...accuracies), Math.max(...accuracies)] : [0, 1]
  const inspected = cell !== null ? history[cell] : bestIndex >= 0 ? history[bestIndex] : undefined
  const active = session?.status === "running" || session?.status === "queued"

  return <div className="page">
    <PageHeader eyebrow={`AUTONOMOUS SEARCH${session ? ` / ${shortId(session.search_id, 8).toUpperCase()}` : ""}`} title="Search laboratory" description="Budgeted searches run on the durable worker against the checksum-verified NATS-Bench archive (evidence: benchmark_lookup). Selection uses validation accuracy only.">
      {session ? <Status tone={statusTone(session.status)}>{(session.status ?? "unknown").toUpperCase()}</Status> : null}
      {session && active ? <button className="button" onClick={() => void cancel(session.search_id)}><Icon name="close" /> Cancel search</button> : null}
      <button className="button primary" onClick={() => go("pareto", session ? { session: session.search_id } : undefined)}>Open Pareto frontier</button>
    </PageHeader>
    <div className="search-grid">
      <Panel title="Search sessions" meta={`${items(searches.data).length} RECORDED`} className="span-2">
        <Loaded poll={searches} label="search sessions" isEmpty={(data) => data.items.length === 0} empty="No search sessions recorded. Launch one with the form on the right.">{(data) => <div className="experiment-list session-list">
          {data.items.map((item) => <button key={item.search_id} className={item.search_id === selectedId ? "active" : ""} onClick={() => setSelectedId(item.search_id)} aria-pressed={item.search_id === selectedId}>
            <span><b className="mono">{item.algorithm} · seed {item.seed}</b><small>{item.search_id.slice(0, 8)} · {item.dataset_id} · budget {item.budget_evaluations ?? "—"}</small></span>
            <Status tone={statusTone(item.status)}>{(item.status ?? "unknown").toUpperCase()}</Status>
            <span className="mono">{(() => { const p = jobProgress(item.job); return p ? `${Math.round(progressFraction(p) * 100)}%` : item.status === "succeeded" ? "100%" : "—" })()}</span>
            <span className="mono muted">{item.job?.updated_at?.slice(11, 19) ?? ""}</span><Icon name="chevron" />
          </button>)}
        </div>}</Loaded>
      </Panel>
      <Panel title="New search" meta="POST /v1/searches">
        <div className="form-body stacked-form">
          <Loaded poll={algorithms} label="policies">{(data) => <label className="field"><span>Policy <em>{chosen?.available === false ? "UNAVAILABLE" : "REGISTRY"}</em></span><select value={form.algorithm} onChange={update("algorithm")}>
            {data.items.map((item) => <option key={item.name} value={item.name} disabled={!item.available}>{item.label}{item.available ? "" : " — unavailable"}</option>)}</select></label>}</Loaded>
          {chosen ? <p className="panel-note">{chosen.description}</p> : null}
          {chosen && !chosen.available ? <Unavailable feature={chosen.label} reason={chosen.unavailable_reason ?? "not installed on this API host"} /> : null}
          <div className="form-grid">
            <label className="field"><span>Dataset</span><input value={form.datasetId} onChange={update("datasetId")} /></label>
            <label className="field"><span>Budget <em>QUERIES</em></span><input inputMode="numeric" value={form.budget} onChange={update("budget")} /></label>
            <label className="field"><span>Seed</span><input inputMode="numeric" value={form.seed} onChange={update("seed")} /></label>
            <label className="field"><span>Search-space indices <em>0:256 OR 1,5,9</em></span><input value={form.indices} onChange={update("indices")} /></label>
          </div>
          <details className="constraint-details"><summary>Constraints (optional)</summary><div className="form-grid"><ConstraintFields form={form} onChange={update} /></div></details>
          <SelectedProjectLabel />
          <button className="button primary" onClick={() => void submit()} disabled={busy}><Icon name="play" /> {busy ? "Launching…" : "Launch search"}</button>
          <ErrorList errors={errors} /><Notice>{message}</Notice>
        </div>
      </Panel>
      <Panel title="Search convergence" meta={history.length ? `${history.length} EVALUATIONS · BENCHMARK_LOOKUP` : "AWAITING RESULTS"} className="span-2">
        {!selectedId ? <EmptyState icon="search" title="No session selected" /> : selected.error ? <div className="load-error" role="alert"><Icon name="alert" size={13} /><span>{selected.error}</span></div>
          : history.length > 1 ? <LineChart label="Validation accuracy per evaluation and best so far" xLabel="evals" yFormat={(value) => value.toFixed(1)}
            series={[{ label: "Best validation accuracy so far", variant: "main", area: true, points: best.map((point) => ({ x: point.step, y: point.best })) },
              { label: "Evaluated validation accuracy", variant: "alt", points: history.map((step) => ({ x: step.step, y: step.validation_accuracy })) }]} />
          : <EmptyState icon="search" title={active ? "Search running on the worker" : `No history yet (status: ${session?.status ?? "loading"})`}>{progress ? <p>{progressLabel(progress)}</p> : <p>Per-step history is reported when the worker finishes the search.</p>}</EmptyState>}
      </Panel>
      <Panel title="Search controller" meta="SESSION">
        {session ? <div className="controller">
          <div className="controller-ring" style={{ background: `radial-gradient(circle at center, var(--panel) 58%, transparent 59%), conic-gradient(var(--teal) ${Math.round(done * 100)}%, #24323c 0)` }} role="progressbar" aria-valuenow={Math.round(done * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Search budget used"><span>{Math.round(done * 100)}%</span><small>BUDGET</small></div>
          {([["Algorithm", session.algorithm], ["Dataset", session.dataset_id], ["Budget", String(budget ?? "—")], ["Seed", String(session.seed)], ["Progress", progress ? progressLabel(progress) : session.status], ["Search id", shortId(session.search_id, 12)]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
          {session.job?.error ? <p className="inline-errors">{session.job.error}</p> : null}
        </div> : <EmptyState icon="search" title="No session selected" />}
      </Panel>
      <Panel title="Population board" meta={history.length ? `${history.length} EVALUATED CELLS` : "NO EVALUATIONS"} className="span-2">
        {history.length ? <>
          <div className="population-grid" role="group" aria-label="Evaluated cells">{history.map((step, index) => <button key={`${step.step}-${step.index}`} aria-label={`Step ${step.step}: cell ${step.index}, ${step.validation_accuracy.toFixed(2)}%`} aria-pressed={cell === index}
            onClick={() => setCell(index)} style={{ opacity: 0.35 + 0.65 * ((step.validation_accuracy - lo) / (hi - lo || 1)) }}
            className={`${index === bestIndex ? "best" : ""} ${cell === index ? "selected" : ""}`}>{index === bestIndex ? "P" : cell === index ? "S" : ""}</button>)}</div>
          {inspected ? <div className="population-detail"><span>{cell === null ? "BEST CELL" : "SELECTED CELL"}</span><code>step {inspected.step} · index {inspected.index}</code><code>{inspected.validation_accuracy.toFixed(2)}% val</code><code>{inspected.params_m !== undefined ? `${inspected.params_m.toFixed(3)} M params` : "params —"}</code>{inspected.architecture_string ? <code className="arch-string" title={inspected.architecture_string}>{inspected.architecture_string}</code> : null}</div> : null}
        </> : <EmptyState icon="search" title="No evaluated cells yet" />}
      </Panel>
      <Panel title="Worker queue" meta={workers.data ? `${workers.data.workers.length} ONLINE` : "WORKERS"}>
        <Loaded poll={workers} label="workers">{(data) => !data.configured ? <Unavailable feature="durable worker" reason="Redis is not configured on the API host." />
          : data.workers.length === 0 ? <div className="empty-inline">No worker heartbeat. Searches stay queued until a worker starts.</div>
          : <div className="worker-list">{data.workers.map((worker) => <div key={worker.worker_id}><i className={worker.active_job_id ? "" : "queued"} /><code>{worker.hostname.slice(0, 10)}</code><span>{worker.active_job_id ? `job ${shortId(worker.active_job_id, 8)}` : "idle"}</span><b>{worker.status}</b></div>)}</div>}</Loaded>
      </Panel>
      {result ? <Panel title="Session result" meta={String(result.evidence_type ?? "").toUpperCase() || "RESULT"} className="span-3 result-panel">
        <div className="table-wrap"><table><tbody>
          <tr><th>Selected cell</th><td><code>{String(result.selected_architecture_string ?? result.selected_index)}</code></td></tr>
          <tr><th>Best validation accuracy (selection)</th><td className="mono">{Number(result.selected_validation_accuracy).toFixed(2)}%</td></tr>
          <tr><th>Held-out test accuracy of selected cell</th><td className="mono">{Number(result.held_out_test_accuracy).toFixed(2)}%</td></tr>
          <tr><th>Queries / evaluations</th><td className="mono">{String(result.queries)} / {String(result.evaluations)}</td></tr>
          {typeof result.hypervolume_validation_params === "number" ? <tr><th>Hypervolume (val %, params M; ref 0, 1.6)</th><td className="mono">{result.hypervolume_validation_params.toFixed(2)}</td></tr> : null}
          <tr><th>Evidence</th><td>{String(result.evidence_type)}</td></tr>
        </tbody></table></div>
        <div className="table-wrap history-table"><table aria-label="Search history"><thead><tr><th>STEP</th><th>INDEX</th><th>VALIDATION %</th><th>PARAMS (M)</th><th>BEST SO FAR</th></tr></thead><tbody>
          {history.map((step, index) => <tr key={`${step.step}-${step.index}`}><td className="mono">{step.step}</td><td className="mono">{step.index}</td><td className="mono">{step.validation_accuracy.toFixed(2)}</td><td className="mono">{step.params_m?.toFixed(3) ?? "—"}</td><td className="mono">{best[index].best.toFixed(2)}</td></tr>)}
        </tbody></table></div>
      </Panel> : null}
    </div>
  </div>
}
