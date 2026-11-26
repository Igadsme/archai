"use client"
import { useState } from "react"
import { Empty, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { getJson } from "../lib/api"
import type { ArchitectureDocument, ArchitectureItem } from "../lib/types"

export default function Architectures() {
  const architectures = items(usePoll<{ items: ArchitectureItem[] }>("/v1/architectures").data)
  const [selected, setSelected] = useState<ArchitectureDocument | null>(null)
  const inspect = async (id: string) => setSelected(await getJson<ArchitectureDocument>(`/v1/architectures/${id}`))
  const metric = (value: number) => new Intl.NumberFormat().format(value)
  return <>
    <PageHeader eyebrow="ARCHITECTURE EXPLORER" title="Validated graphs" note="Every record is a canonical, hash-addressed DAG validated by archai_core." />
    <div className="grid">
      <article className="panel"><h3>Registry</h3>{architectures.length === 0 ? <Empty>No architecture records yet.</Empty> : <ul>{architectures.map((item) => <li key={item.architecture_id}><button className="link-button" onClick={() => void inspect(item.architecture_id)}><code>{item.architecture_id.slice(0, 12)}</code></button><span>{metric(item.metrics.parameters)} params · {metric(item.metrics.flops)} FLOPs</span></li>)}</ul>}</article>
      <article className="panel"><h3>Graph</h3>{selected ? <><p className="muted"><code>{selected.hash.slice(0, 16)}</code> · {selected.architecture.nodes.length} nodes · {selected.architecture.edges.length} edges</p><div className="node-strip">{selected.architecture.nodes.map((node) => <span className="node-chip" key={node.id}><strong>{node.id}</strong><small>{node.op} · {node.channels}ch</small></span>)}</div><div className="edge-list">{selected.architecture.edges.map((edge) => <span key={`${edge.source}-${edge.target}`}><code>{edge.source}</code> → <code>{edge.target}</code></span>)}</div></> : <Empty>Select an architecture to inspect its graph.</Empty>}</article>
    </div>
  </>
}
