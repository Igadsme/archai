"use client"
import Link from "next/link"
import { ProjectPicker } from "./components/ProjectPicker"
import { Empty, Loaded, PageHeader } from "./components/Shell"
import { items, usePoll } from "./components/usePoll"
import { ci, splitAblations } from "./lib/results"
import type { ArchitectureItem, ExperimentItem, JobItem, ModelItem, Readiness, ResearchResult, SearchItem } from "./lib/types"

export default function ResearchDashboard() {
  const architectures = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures")
  const searches = usePoll<{ items: SearchItem[] }>("/v1/searches")
  const experiments = usePoll<{ items: ExperimentItem[] }>("/v1/experiments")
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs")
  const models = usePoll<{ items: ModelItem[] }>("/v1/models")
  const readiness = usePoll<Readiness>("/readiness")
  const suite = usePoll<ResearchResult>("/v1/research/results/nasbench201_cifar10_full_suite", 0)
  const count = (poll: { data: { items?: unknown[] } | null; error: string | null }) => poll.error ? "—" : String(items(poll.data).length)
  const failed = items(jobs.data).filter((job) => job.status === "failed")
  const cards: [string, string, string, string][] = [
    ["Architectures", count(architectures), "validated, hash-addressed", "/explorer"],
    ["Search sessions", count(searches), `${items(searches.data).filter((s) => s.status === "running").length} running`, "/search"],
    ["Experiments", count(experiments), `${items(experiments.data).filter((e) => e.status === "completed").length} completed`, "/results"],
    ["Jobs", count(jobs), `${failed.length} failed`, "/training"],
    ["Checkpoints", count(models), "integrity-checked", "/models"],
  ]
  return <>
    <PageHeader eyebrow="RESEARCH DASHBOARD" title="Controlled discovery workspace"
      note={readiness.data ? `Readiness: ${readiness.data.status} · rate limits: ${readiness.data.rate_limit_backend ?? "unknown"}` : `API: ${readiness.error ?? "checking"}`} />
    <div className="cards">{cards.map(([label, value, note, href]) => <Link className="card-link" href={href} key={label}><article><span className="label">{label}</span><strong>{value}</strong><small>{note}</small></article></Link>)}</div>
    <div className="grid">
      <ProjectPicker />
      <article className="panel"><p className="eyebrow">MEASURED BENCHMARK (benchmark_lookup)</p><h3>Best validation accuracy at 100 queries</h3>
        <Loaded poll={suite}>{(data) => data.report ? <table><thead><tr><th>Policy</th><th>Mean [95% CI], 10 seeds</th></tr></thead><tbody>
          {splitAblations(data).policies.map((name) => <tr key={name}><td>{name}</td><td className="num">{ci(data.report!.algorithms[name].best_validation_accuracy)}</td></tr>)}
        </tbody></table> : <Empty>No report in this result set.</Empty>}</Loaded>
        <p><Link href="/results">All measured results →</Link></p></article>
      <article className="panel"><p className="eyebrow">ERRORS</p><h3>Failed jobs</h3>
        <Loaded poll={jobs} isEmpty={() => failed.length === 0} empty="No failed jobs.">{() => <ul>{failed.slice(0, 8).map((job) => <li key={job.job_id}><code>{job.kind} · {job.job_id.slice(0, 8)}</code><span className="error-text">{job.error}</span></li>)}</ul>}</Loaded></article>
    </div>
  </>
}
