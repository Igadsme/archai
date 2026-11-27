"use client"
import { useState } from "react"
import { DagView } from "../components/DagView"
import { Empty, Errors, Loaded, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { downloadFile, fetchJson, postJson } from "../lib/api"
import { defaultCandidateArchitecture } from "../lib/forms"
import type { AnalyticalMetrics, ArchitectureItem, FullArchitecture } from "../lib/types"

type Detail = { architecture: FullArchitecture; hash: string; analytical_metrics: AnalyticalMetrics }

export default function ArchitectureGraphExplorer() {
  const registry = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures")
  const [selected, setSelected] = useState<Detail | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [draft, setDraft] = useState(JSON.stringify(defaultCandidateArchitecture, null, 1))
  const [message, setMessage] = useState("")
  const inspect = async (id: string) => {
    const outcome = await fetchJson<Detail>(`/v1/architectures/${id}`)
    if (outcome.ok) { setSelected(outcome.data); setErrors([]) } else setErrors([`${outcome.status}: ${outcome.detail}`])
  }
  const exportAs = async (format: "json" | "pytorch") => {
    if (!selected) return
    const error = await downloadFile(`/v1/architectures/${selected.hash}/export?format=${format}`, `${selected.hash.slice(0, 16)}.${format === "json" ? "json" : "pt"}`)
    setErrors(error ? [`Export failed: ${error}`] : [])
    setMessage(error ? "" : format === "pytorch" ? "Downloaded a TorchScript module; load it with torch.jit.load(path)." : "Downloaded canonical JSON.")
  }
  const register = async () => {
    let body: unknown
    try { body = JSON.parse(draft) } catch { setErrors(["architecture must be valid JSON"]); return }
    const outcome = await postJson<{ hash: string }>("/v1/architectures", body)
    if (outcome.ok) { setErrors([]); setMessage(`Registered ${outcome.data.hash.slice(0, 12)}.`); registry.refresh(); void inspect(outcome.data.hash) }
    else setErrors([`${outcome.status}: ${outcome.detail}`])
  }
  const n = (value: number) => new Intl.NumberFormat().format(value)
  return <>
    <PageHeader eyebrow="ARCHITECTURE GRAPH EXPLORER" title="Inspect, validate and export graphs" note="Every record is a canonical, hash-addressed DAG validated by archai_core." />
    <div className="grid">
      <article className="panel"><h3>Registry</h3>
        <Loaded poll={registry} isEmpty={(data) => items(data).length === 0} empty="No architecture records yet. Register one below.">
          {(data) => <ul>{items(data).map((item) => <li key={item.architecture_id}><button className="link-button" onClick={() => void inspect(item.architecture_id)}><code>{item.architecture_id.slice(0, 12)}</code></button><span>{n(item.metrics.parameters)} params · {n(item.metrics.flops)} FLOPs</span></li>)}</ul>}
        </Loaded>
        <h3>Register an architecture</h3>
        <label>Architecture JSON (validated by the API)<textarea rows={7} value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
        <button onClick={() => void register()}>Validate and register</button>
      </article>
      <article className="panel"><h3>Graph</h3>
        <Errors errors={errors} />{message ? <p className="muted" role="status">{message}</p> : null}
        {selected ? <>
          <p className="muted"><code>{selected.hash.slice(0, 16)}</code> · {selected.architecture.nodes.length} nodes · {selected.architecture.edges.length} edges · {n(selected.analytical_metrics.parameters)} params · {n(selected.analytical_metrics.flops)} FLOPs</p>
          <DagView architecture={selected.architecture} />
          <div className="form-row"><button onClick={() => void exportAs("json")}>Export JSON</button><button onClick={() => void exportAs("pytorch")}>Export PyTorch (TorchScript)</button></div>
        </> : <Empty>Select an architecture to inspect its graph.</Empty>}
      </article>
    </div>
  </>
}
