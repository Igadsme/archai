"use client"

import { useEffect, useState } from "react"

type ArchitectureItem = { architecture_id: string; search_space: string; metrics: { parameters: number; flops: number; activation_memory_bytes: number } }
type ArchitectureResponse = { items: ArchitectureItem[] }
const apiBase = process.env.NEXT_PUBLIC_ARCHAI_API_URL ?? "http://127.0.0.1:8000"

export default function Home() {
  const [architectures, setArchitectures] = useState<ArchitectureItem[]>([])
  const [apiState, setApiState] = useState("checking")
  useEffect(() => {
    fetch(`${apiBase}/health`).then((response) => setApiState(response.ok ? "ready" : "unavailable")).catch(() => setApiState("unavailable"))
    fetch(`${apiBase}/v1/architectures`).then((response) => response.json() as Promise<ArchitectureResponse>).then((payload) => setArchitectures(payload.items ?? [])).catch(() => setArchitectures([]))
  }, [])
  const metric = (value: number) => new Intl.NumberFormat().format(value)
  return <main className="shell">
    <aside className="sidebar">
      <p className="eyebrow">ARCHAI STUDIO</p><h1>AI that designs AI.</h1><p className="muted">Evidence-aware neural architecture research.</p>
      <nav><a className="active" href="#overview">Overview</a><a href="#generator">Generator</a><a href="#search">Search laboratory</a><a href="#registry">Model registry</a></nav>
      <div className="status"><span className={`dot ${apiState}`} /> API {apiState}</div>
    </aside>
    <section className="content" id="overview">
      <header className="topbar"><div><p className="eyebrow">RESEARCH OVERVIEW</p><h2>Controlled discovery workspace</h2></div><span className="badge">No fabricated metrics</span></header>
      <div className="cards"><article><span className="label">Registered architectures</span><strong>{architectures.length}</strong><small>API-backed records</small></article><article><span className="label">Search sessions</span><strong>—</strong><small>Worker not configured</small></article><article><span className="label">Trained checkpoints</span><strong>—</strong><small>Awaiting provenance</small></article><article><span className="label">Benchmark status</span><strong>Pending</strong><small>Checksum required</small></article></div>
      <div className="grid"><article className="panel wide" id="generator"><div className="panel-head"><div><p className="eyebrow">GENERATOR</p><h3>Candidate architecture generation</h3></div><button disabled>Generate candidates</button></div><p className="muted">Generation is disabled until a trained, provenance-backed checkpoint is configured.</p><div className="empty">Configure a real generator checkpoint and task dataset to begin.</div></article><article className="panel" id="search"><p className="eyebrow">SEARCH LABORATORY</p><h3>Closed-loop experiments</h3><div className="empty">No durable worker is connected. Search start requests are preserved as explicit API errors.</div></article><article className="panel" id="registry"><p className="eyebrow">ARCHITECTURE REGISTRY</p><h3>Recent records</h3>{architectures.length === 0 ? <div className="empty">No architecture records yet.</div> : <ul>{architectures.slice(0, 5).map((item) => <li key={item.architecture_id}><code>{item.architecture_id.slice(0, 12)}</code><span>{metric(item.metrics.parameters)} params</span></li>)}</ul>}</article></div>
    </section>
  </main>
}
