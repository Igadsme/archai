"use client"
import Link from "next/link"
import { Empty, PageHeader } from "./components/Shell"
import { items, usePoll } from "./components/usePoll"
import type { ArchitectureItem, DatasetItem, ExperimentItem, JobItem, ModelItem, Readiness, SearchItem } from "./lib/types"

export default function Overview() {
  const architectures = items(usePoll<{ items: ArchitectureItem[] }>("/v1/architectures").data)
  const searches = items(usePoll<{ items: SearchItem[] }>("/v1/searches").data)
  const experiments = items(usePoll<{ items: ExperimentItem[] }>("/v1/experiments").data)
  const datasets = items(usePoll<{ items: DatasetItem[] }>("/v1/datasets").data)
  const jobs = items(usePoll<{ items: JobItem[] }>("/v1/jobs").data)
  const models = items(usePoll<{ items: ModelItem[] }>("/v1/models").data)
  const readiness = usePoll<Readiness>("/readiness").data
  const cards: [string, number, string, string][] = [
    ["Architectures", architectures.length, "API-backed records", "/architectures"],
    ["Search sessions", searches.length, `${searches.filter((item) => item.status === "running").length} running`, "/search"],
    ["Experiments", experiments.length, `${experiments.filter((item) => item.status === "completed").length} completed`, "/experiments"],
    ["Datasets", datasets.length, "Checksum-registered", "/datasets"],
    ["Jobs", jobs.length, `${jobs.filter((item) => item.status === "running").length} running`, "/training"],
  ]
  return <>
    <PageHeader eyebrow="RESEARCH OVERVIEW" title="Controlled discovery workspace" note={readiness ? `Readiness: ${readiness.status} · rate limits: ${readiness.rate_limit_backend ?? "unknown"}` : "API unreachable"} />
    <div className="cards">{cards.map(([label, value, note, href]) => <Link className="card-link" href={href} key={label}><article><span className="label">{label}</span><strong>{value}</strong><small>{note}</small></article></Link>)}</div>
    <div className="grid">
      <article className="panel"><p className="eyebrow">EVIDENCE LOG</p><h3>Recent experiments</h3>{experiments.length === 0 ? <Empty>No experiment evidence recorded.</Empty> : <ul>{experiments.slice(0, 6).map((item) => <li key={item.experiment_id}><code>{item.evidence_type}</code><span>{item.status}</span></li>)}</ul>}</article>
      <article className="panel"><p className="eyebrow">MODEL REGISTRY</p><h3>Checkpoints</h3>{models.length === 0 ? <Empty>No model checkpoints registered.</Empty> : <ul>{models.slice(0, 6).map((item) => <li key={`${item.model_id}-${item.version}`}><code>{item.model_id}</code><span>{item.kind} · {item.version}</span></li>)}</ul>}</article>
    </div>
  </>
}
