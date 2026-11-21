"use client"

import { useEffect, useState } from "react"

type ArchitectureItem = { architecture_id: string; search_space: string; metrics: { parameters: number; flops: number; activation_memory_bytes: number } }
type ArchitectureResponse = { items: ArchitectureItem[] }
type SearchItem = { search_id: string; algorithm: string; dataset_id: string; status: string; seed: number }
type ExperimentItem = { experiment_id: string; architecture_id: string; evidence_type: string; status: string; metrics: Record<string, number> }
type DatasetItem = { dataset_id: string; version: string; checksum: string }
type JobItem = { job_id: string; kind: string; status: string; error: string | null }
type ModelItem = { model_id: string; kind: string; version: string; checksum: string }
type ArchitectureDocument = { architecture: { nodes: { id: string; op: string; channels: number }[]; edges: { source: string; target: string }[] }; hash: string }
const apiBase = process.env.NEXT_PUBLIC_ARCHAI_API_URL ?? "http://127.0.0.1:8000"

export default function Home() {
  const [architectures, setArchitectures] = useState<ArchitectureItem[]>([])
  const [searches, setSearches] = useState<SearchItem[]>([])
  const [experiments, setExperiments] = useState<ExperimentItem[]>([])
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [jobs, setJobs] = useState<JobItem[]>([])
  const [models, setModels] = useState<ModelItem[]>([])
  const [selectedArchitecture, setSelectedArchitecture] = useState<ArchitectureDocument | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [apiState, setApiState] = useState("checking")
  useEffect(() => {
    const load = async () => {
      try {
        const health = await fetch(`${apiBase}/health`)
        setApiState(health.ok ? "ready" : "unavailable")
        const [architectureResponse, searchResponse, experimentResponse, datasetResponse, jobResponse, modelResponse] = await Promise.all([
          fetch(`${apiBase}/v1/architectures`), fetch(`${apiBase}/v1/searches`),
          fetch(`${apiBase}/v1/experiments`), fetch(`${apiBase}/v1/datasets`),
          fetch(`${apiBase}/v1/jobs`), fetch(`${apiBase}/v1/models`),
        ])
        if (architectureResponse.ok) setArchitectures((await architectureResponse.json() as ArchitectureResponse).items ?? [])
        if (searchResponse.ok) setSearches((await searchResponse.json() as { items: SearchItem[] }).items ?? [])
        if (experimentResponse.ok) setExperiments((await experimentResponse.json() as { items: ExperimentItem[] }).items ?? [])
        if (datasetResponse.ok) setDatasets((await datasetResponse.json() as { items: DatasetItem[] }).items ?? [])
        if (jobResponse.ok) setJobs((await jobResponse.json() as { items: JobItem[] }).items ?? [])
        if (modelResponse.ok) setModels((await modelResponse.json() as { items: ModelItem[] }).items ?? [])
        setLastUpdated(new Date())
      } catch {
        setApiState("unavailable")
      }
    }
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [])
  const inspectArchitecture = async (architectureId: string) => {
    try {
      const response = await fetch(`${apiBase}/v1/architectures/${architectureId}`)
      if (response.ok) setSelectedArchitecture(await response.json() as ArchitectureDocument)
    } catch { setSelectedArchitecture(null) }
  }
  const metric = (value: number) => new Intl.NumberFormat().format(value)
  return <main className="shell">
    <aside className="sidebar">
      <p className="eyebrow">ARCHAI STUDIO</p><h1>AI that designs AI.</h1><p className="muted">Evidence-aware neural architecture research.</p>
      <nav><a className="active" href="#overview">Overview</a><a href="#generator">Generator</a><a href="#search">Search laboratory</a><a href="#registry">Model registry</a></nav>
      <div className="status"><span className={`dot ${apiState}`} /> API {apiState}</div>
    </aside>
    <section className="content" id="overview">
      <header className="topbar"><div><p className="eyebrow">RESEARCH OVERVIEW</p><h2>Controlled discovery workspace</h2><small>{lastUpdated ? `Live refresh · ${lastUpdated.toLocaleTimeString()}` : "Loading live state…"}</small></div><span className="badge">No fabricated metrics</span></header>
      <div className="cards"><article><span className="label">Registered architectures</span><strong>{architectures.length}</strong><small>API-backed records</small></article><article><span className="label">Search sessions</span><strong>{searches.length}</strong><small>{searches.filter((item) => item.status === "running").length} running</small></article><article><span className="label">Experiments</span><strong>{experiments.length}</strong><small>{experiments.filter((item) => item.status === "completed").length} completed</small></article><article><span className="label">Datasets</span><strong>{datasets.length}</strong><small>Checksum-registered</small></article><article><span className="label">Jobs</span><strong>{jobs.length}</strong><small>{jobs.filter((item) => item.status === "running").length} running</small></article></div>
      <div className="grid"><article className="panel wide" id="generator"><div className="panel-head"><div><p className="eyebrow">GENERATOR</p><h3>Candidate architecture generation</h3></div><button disabled>Generate candidates</button></div><p className="muted">Generation is disabled until a trained, provenance-backed checkpoint is configured.</p><div className="empty">Configure a real generator checkpoint and task dataset to begin.</div></article><article className="panel" id="search"><p className="eyebrow">SEARCH LABORATORY</p><h3>Recent sessions</h3>{searches.length === 0 ? <div className="empty">No search sessions recorded.</div> : <ul>{searches.slice(0, 5).map((item) => <li key={item.search_id}><code>{item.algorithm}</code><span>{item.status} · {item.dataset_id}</span></li>)}</ul>}</article><article className="panel" id="registry"><p className="eyebrow">ARCHITECTURE REGISTRY</p><h3>Recent records</h3>{architectures.length === 0 ? <div className="empty">No architecture records yet.</div> : <ul>{architectures.slice(0, 5).map((item) => <li key={item.architecture_id}><button className="link-button" onClick={() => void inspectArchitecture(item.architecture_id)}><code>{item.architecture_id.slice(0, 12)}</code></button><span>{metric(item.metrics.parameters)} params</span></li>)}</ul>}</article><article className="panel"><p className="eyebrow">EVIDENCE LOG</p><h3>Recent experiments</h3>{experiments.length === 0 ? <div className="empty">No experiment evidence recorded.</div> : <ul>{experiments.slice(0, 5).map((item) => <li key={item.experiment_id}><code>{item.evidence_type}</code><span>{item.status}</span></li>)}</ul>}</article><article className="panel"><p className="eyebrow">MODEL REGISTRY</p><h3>Checkpoint artifacts</h3>{models.length === 0 ? <div className="empty">No model checkpoints registered.</div> : <ul>{models.slice(0, 5).map((item) => <li key={item.model_id}><code>{item.model_id}</code><span>{item.kind} · {item.version}</span></li>)}</ul>}</article><article className="panel"><p className="eyebrow">WORKER MONITOR</p><h3>Durable jobs</h3>{jobs.length === 0 ? <div className="empty">No jobs recorded.</div> : <ul>{jobs.slice(0, 5).map((item) => <li key={item.job_id}><code>{item.kind}</code><span className={`job-${item.status}`}>{item.status}</span></li>)}</ul>}</article><article className="panel wide" id="visualization"><p className="eyebrow">ARCHITECTURE INSPECTOR</p><h3>Graph visualization</h3>{selectedArchitecture ? <><p className="muted"><code>{selectedArchitecture.hash.slice(0, 16)}</code> · {selectedArchitecture.architecture.nodes.length} nodes · {selectedArchitecture.architecture.edges.length} edges</p><div className="node-strip">{selectedArchitecture.architecture.nodes.map((node) => <span className="node-chip" key={node.id}><strong>{node.id}</strong><small>{node.op} · {node.channels}ch</small></span>)}</div><div className="edge-list">{selectedArchitecture.architecture.edges.map((edge) => <span key={`${edge.source}-${edge.target}`}><code>{edge.source}</code> → <code>{edge.target}</code></span>)}</div></> : <div className="empty">Select an architecture ID above to inspect its validated graph.</div>}</article></div>
    </section>
  </main>
}
