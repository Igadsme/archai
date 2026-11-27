"use client"
import { useEffect, useMemo, useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { announce, describeFailure, downloadJson, postJson } from "../lib/api"
import { jobProgress, progressLabel } from "../lib/progress"
import { jobResult } from "../lib/results"
import type { ExperimentItem, JobDetail, JobItem } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { useGo, useQueryParam } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { EmptyState, Loaded, PageHeader, Panel, shortId, Status, statusTone } from "../studio/ui"

export type JobFilter = "all" | "failed" | "active" | "succeeded"

export function filterJobs(jobs: JobItem[], filter: JobFilter, query: string): JobItem[] {
  const needle = query.trim().toLowerCase()
  return jobs.filter((job) => (filter === "all" || (filter === "failed" ? job.status === "failed" : filter === "active" ? job.status === "queued" || job.status === "running" : job.status === "succeeded"))
    && (!needle || job.job_id.toLowerCase().includes(needle) || job.kind.toLowerCase().includes(needle) || (job.error ?? "").toLowerCase().includes(needle)))
}

export function Experiments() {
  const go = useGo()
  const requested = useQueryParam("job")
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs", 5_000, itemsResponse)
  const experiments = usePoll<{ items: ExperimentItem[] }>("/v1/experiments", 15_000, itemsResponse)
  const [filter, setFilter] = useState<JobFilter>("all")
  const [query, setQuery] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const retry = async (id: string) => {
    setRetrying(true)
    const outcome = await postJson<JobItem>(`/v1/jobs/${encodeURIComponent(id)}/retry`, {})
    setRetrying(false)
    if (!outcome.ok) { announce(`Retry failed — ${describeFailure(outcome)}`); return }
    announce(`Queued retry ${outcome.data.job_id.slice(0, 8)} of ${id.slice(0, 8)}.`)
    jobs.refresh()
    setJobId(outcome.data.job_id)
  }
  const detail = usePoll<JobDetail>(jobId ? `/v1/jobs/${encodeURIComponent(jobId)}` : null, 4_000)
  useEffect(() => { if (requested) setJobId(requested) }, [requested])
  const all = items(jobs.data)
  const visible = useMemo(() => filterJobs(all, filter, query), [all, filter, query])
  useEffect(() => { if (!jobId && !requested && visible[0]) setJobId(visible[0].job_id) }, [jobId, requested, visible])
  const counts = { all: all.length, failed: all.filter((job) => job.status === "failed").length, active: all.filter((job) => job.status === "queued" || job.status === "running").length, succeeded: all.filter((job) => job.status === "succeeded").length }
  const job = detail.data
  const result = jobResult(job)
  const progress = jobProgress(job)
  const searchId = typeof job?.payload?.search_id === "string" ? job.payload.search_id : null
  const metrics: [string, string][] = job ? [["KIND", job.kind], ["STATUS", job.status.toUpperCase()], ["CREATED", job.created_at?.slice(11, 19) ?? "—"], ["UPDATED", job.updated_at?.slice(11, 19) ?? "—"]] : []
  const timeline = job ? ([["Created", job.created_at], ["Progress reported", progress?.reported_at], [job.status === "queued" || job.status === "running" ? "Last update" : `Finished (${job.status})`, job.updated_at]] as [string, string | null | undefined][]) : []

  return <div className="page">
    <PageHeader eyebrow="EXPERIMENT HISTORY" title="Experiment history" description="Every job the API has recorded (searches, training, research suites) with its timeline, error and stored result, plus experiments recorded through /v1/experiments.">
      <Status tone={counts.failed ? "red" : "teal"}>{counts.failed} FAILED · {counts.active} ACTIVE</Status>
    </PageHeader>
    <div className="experiment-layout">
      <Panel title="Jobs" meta={`${visible.length} OF ${all.length}`}
        actions={<div className="segmented" role="group" aria-label="Job filter">{([["all", "All"], ["failed", "Failed only"], ["active", "Active"], ["succeeded", "Succeeded"]] as [JobFilter, string][]).map(([value, label]) => <button key={value} className={filter === value ? "active" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label} {counts[value]}</button>)}</div>}>
        <div className="list-search"><Icon name="search" size={13} /><input aria-label="Filter jobs" placeholder="Filter by id, kind or error" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
        <Loaded poll={jobs} label="jobs" isEmpty={() => visible.length === 0} empty={all.length ? "No jobs match this filter." : "No jobs recorded yet."}>{() => <div className="experiment-list">
          {visible.map((item) => <button key={item.job_id} className={item.job_id === jobId ? "active" : ""} aria-pressed={item.job_id === jobId} onClick={() => setJobId(item.job_id)}>
            <span><b className="mono">{item.kind}</b><small>{item.job_id.slice(0, 12)} · {item.created_at?.replace("T", " ").slice(0, 19) ?? ""}</small></span>
            <Status tone={statusTone(item.status)}>{item.status.toUpperCase()}</Status>
            <span className="mono muted">{(() => { const p = jobProgress(item); return p ? progressLabel(p) : "" })()}</span>
            <span className="mono error-text">{item.error ? "ERROR" : ""}</span><Icon name="chevron" />
          </button>)}
        </div>}</Loaded>
      </Panel>
      <Panel title="Run detail" meta={job ? shortId(job.job_id, 12).toUpperCase() : "NONE"}>
        {!jobId ? <EmptyState icon="experiments" title="Select a job" /> : detail.error ? <div className="load-error" role="alert"><Icon name="alert" size={13} /><span>{detail.error}</span><button className="button compact" onClick={detail.refresh}>Retry</button></div> : !job ? <div className="loading-state" role="status"><i />Loading job…</div> : <>
          <div className="run-detail-head"><div><span>{job.kind.toUpperCase()}</span><h2 className="mono">{job.job_id}</h2></div>
            <div className="inspector-actions">
              <button className="button compact" onClick={() => downloadJson(`archai-job-${job.job_id.slice(0, 8)}.json`, { exported_at: new Date().toISOString(), evidence: "API job record as returned by GET /v1/jobs/{id}", job })}><Icon name="download" size={12} /> Export</button>
              {searchId ? <button className="button compact" onClick={() => go("search", { session: searchId })}>Open search</button> : null}
              {job.kind === "training" || job.kind.endsWith("_training") ? <button className="button compact" onClick={() => go("training", { job: job.job_id })}>Open training</button> : null}
              {(job.status === "failed" || job.status === "cancelled") && job.kind !== "experiment" ? <button className="button compact" disabled={retrying} onClick={() => void retry(job.job_id)}>{retrying ? "Retrying…" : "Retry"}</button> : null}
              {typeof job.payload?.retried_as === "string" ? <button className="button compact" onClick={() => setJobId(job.payload?.retried_as as string)}>Open retry</button> : null}
              {typeof job.payload?.retry_of === "string" ? <button className="button compact" onClick={() => setJobId(job.payload?.retry_of as string)}>Open original</button> : null}
            </div></div>
          <div className="detail-metrics">{metrics.map(([label, value]) => <span key={label}><small>{label}</small><b>{value}</b></span>)}</div>
          {job.error ? <div className="error-state" role="alert"><div><span>!</span><h3>Job failed</h3></div><pre>{job.error}</pre></div> : null}
          <div className="timeline"><h3>TIMELINE</h3>{timeline.map(([label, at]) => <div key={label} className={at ? "done" : "pending"}><i /><span>{label}</span><time>{at ? at.replace("T", " ").slice(0, 19) : "—"}</time></div>)}
            {progress ? <div className="done"><i /><span>{progressLabel(progress)}</span><time>{progress.phase}</time></div> : null}</div>
          <div className="timeline"><h3>PAYLOAD</h3><pre className="result-json">{JSON.stringify(Object.fromEntries(Object.entries(job.payload ?? {}).filter(([key]) => key !== "result" && key !== "progress")), null, 1)}</pre></div>
          <div className="timeline"><h3>RESULT</h3>{result ? <pre className="result-json">{JSON.stringify(result, null, 1)}</pre> : <div className="empty-inline">No stored result (status: {job.status}).</div>}</div>
        </>}
      </Panel>
      <Panel title="Recorded experiments" meta="/v1/experiments" className="span-all">
        <Loaded poll={experiments} label="experiments" isEmpty={(data) => data.items.length === 0} empty="No experiments recorded through the API.">{(data) => <div className="table-wrap"><table aria-label="Recorded experiments"><thead><tr><th>EXPERIMENT</th><th>ARCHITECTURE</th><th>EVIDENCE</th><th>STATUS</th><th>METRICS</th><th>DATASET · SEED</th></tr></thead><tbody>
          {data.items.map((item) => <tr key={item.experiment_id}><td><code>{item.experiment_id.slice(0, 12)}</code></td><td><button className="link-button mono" onClick={() => go("explorer", { id: item.architecture_id })}>{item.architecture_id.slice(0, 12)}</button></td><td>{item.evidence_type}</td><td><Status tone={statusTone(item.status)}>{item.status.toUpperCase()}</Status></td>
            <td className="mono">{Object.entries(item.metrics ?? {}).map(([key, value]) => `${key}=${typeof value === "number" ? value.toFixed(3) : value}`).join(" · ") || "—"}</td><td className="mono">{item.provenance?.dataset_id ?? "—"} · {item.provenance?.seed ?? "—"}</td></tr>)}
        </tbody></table></div>}</Loaded>
      </Panel>
    </div>
  </div>
}
