"use client"
import { useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { describeFailure, downloadFile, fetchJson } from "../lib/api"
import type { ArchitectureDetail, ArchitectureItem, ModelInspection, ModelItem } from "../lib/types"
import { architectureDetailResponse, itemsResponse } from "../lib/validators"
import { useGo } from "../studio/hooks"
import { Deployments } from "./Deployments"
import { Icon } from "../studio/Icon"
import { MiniGraph } from "../studio/MiniGraph"
import { EmptyState, ErrorList, formatBytes, formatCompact, formatCount, Loaded, PageHeader, Panel, shortId, Status } from "../studio/ui"

type Tab = "architectures" | "checkpoints" | "deployments"

export function integrityLabel(item: ModelItem): { text: string; tone: "teal" | "red" | "gray" } {
  if (item.integrity_verified === undefined) return { text: "NOT CHECKED", tone: "gray" }
  if (item.integrity_verified) return { text: "SHA-256 VERIFIED", tone: "teal" }
  return { text: item.artifact_exists === false ? "FILE MISSING" : "CHECKSUM MISMATCH", tone: "red" }
}

export function Registry() {
  const go = useGo()
  const [tab, setTab] = useState<Tab>("architectures")
  const [query, setQuery] = useState("")
  const architectures = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures?limit=200", 15_000, itemsResponse)
  const models = usePoll<{ items: ModelItem[] }>("/v1/models", 15_000, itemsResponse)
  const deploymentCount = usePoll<{ items: unknown[] }>("/v1/deployments", 15_000, itemsResponse)
  const [archId, setArchId] = useState<string | null>(null)
  const archDetail = usePoll<ArchitectureDetail>(archId ? `/v1/architectures/${encodeURIComponent(archId)}` : null, 0, architectureDetailResponse)
  const [inspection, setInspection] = useState<ModelInspection | null>(null)
  const [inspecting, setInspecting] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const needle = query.trim().toLowerCase()
  const archs = items(architectures.data).filter((item) => !needle || item.architecture_id.includes(needle) || item.search_space.toLowerCase().includes(needle))
  const checkpoints = items(models.data).filter((item) => !needle || item.model_id.toLowerCase().includes(needle) || item.kind.toLowerCase().includes(needle))
  const inspect = async (item: ModelItem) => {
    setInspecting(`${item.model_id}@${item.version}`); setErrors([])
    const outcome = await fetchJson<ModelInspection>(`/v1/models/${encodeURIComponent(item.model_id)}/inspect?version=${encodeURIComponent(item.version)}`, { timeoutMs: 60_000 })
    setInspecting(null)
    if (outcome.ok) setInspection(outcome.data); else { setInspection(null); setErrors([`Inspection failed — ${describeFailure(outcome)}`]) }
  }
  const exportArch = async (format: "json" | "pytorch") => {
    if (!archId) return
    const failure = await downloadFile(`/v1/architectures/${encodeURIComponent(archId)}/export?format=${format}`, `archai-${archId.slice(0, 12)}.${format === "json" ? "json" : "pt"}`)
    setErrors(failure ? [failure] : [])
  }

  return <div className="page">
    <PageHeader eyebrow="MODEL REGISTRY" title="Model registry" description="Registered architectures (content-addressed by SHA-256 of the canonical graph) and checksum-backed checkpoints. Integrity is re-verified on every read; inspection refuses a file whose checksum no longer matches.">
      <Status tone="teal">{items(architectures.data).length} ARCHITECTURES · {items(models.data).length} CHECKPOINTS</Status>
      <button className="button" onClick={() => go("generator")}><Icon name="generator" /> Generate architectures</button>
    </PageHeader>
    <div className="registry-tabs" role="tablist" aria-label="Registry sections">
      {([["architectures", `ARCHITECTURES ${items(architectures.data).length}`], ["checkpoints", `CHECKPOINTS ${items(models.data).length}`], ["deployments", `DEPLOYMENTS ${items(deploymentCount.data).length}`]] as [Tab, string][]).map(([value, label]) => <button key={value} role="tab" aria-selected={tab === value} className={tab === value ? "active" : ""} onClick={() => setTab(value)}>{label}</button>)}
      <div className="list-search registry-search"><Icon name="search" size={13} /><input aria-label="Search registry" placeholder="Search id, kind or search space" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
    </div>
    {tab === "architectures" ? <div className="registry-workspace">
      <Panel title="Registered architectures" meta={`${archs.length} SHOWN · /v1/architectures`}>
        <Loaded poll={architectures} label="architectures" isEmpty={() => archs.length === 0} empty={needle ? "No architectures match this search." : "No architectures registered. Register one from the Explorer or Generator."}>{() => <div className="registry-list">
          {archs.map((item) => <div key={item.architecture_id} className={item.architecture_id === archId ? "active" : ""}>
            <Icon name="layers" /><button className="link-button" onClick={() => setArchId(item.architecture_id)} aria-pressed={item.architecture_id === archId}><b className="mono">{item.architecture_id.slice(0, 16)}</b><small>{item.search_space}</small></button>
            <span className="mono">{formatCompact(item.metrics.parameters)}<small>params</small></span><span className="mono">{formatCompact(item.metrics.flops)}<small>FLOPs</small></span>
            <span className="badge">ANALYTICAL</span><button className="icon-button" aria-label={`Open ${item.architecture_id.slice(0, 12)} in explorer`} onClick={() => go("explorer", { id: item.architecture_id })}><Icon name="explorer" size={14} /></button>
          </div>)}
        </div>}</Loaded>
      </Panel>
      <Panel title="Architecture detail" meta={archId ? shortId(archId, 12).toUpperCase() : "NONE"}>
        {!archId ? <EmptyState icon="registry" title="Select an architecture" /> : <Loaded poll={archDetail} label="architecture">{(data) => <div className="registry-detail">
          <MiniGraph architecture={data.architecture} label={`Graph of ${archId.slice(0, 12)}`} />
          {([["Content hash", data.hash], ["Search space", data.architecture.search_space ?? "—"], ["Nodes / edges", `${data.architecture.nodes.length} / ${data.architecture.edges.length}`], ["Input", data.architecture.input_spec ? `${data.architecture.input_spec.channels}×${data.architecture.input_spec.height}×${data.architecture.input_spec.width}` : "—"], ["Output classes", String(data.architecture.output_classes ?? "—")],
            ["Parameters", formatCount(data.analytical_metrics.parameters)], ["FLOPs", formatCount(data.analytical_metrics.flops)], ["Activation memory", formatBytes(data.analytical_metrics.activation_memory_bytes)], ["Generator", data.architecture.generator_version ?? "—"], ["Seed", String(data.architecture.seed ?? "—")]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
          <div className="inspector-actions">
            <button className="button primary" onClick={() => go("explorer", { id: archId })}><Icon name="explorer" /> Open in explorer</button>
            <button className="button" onClick={() => void exportArch("json")}><Icon name="download" /> Export JSON</button>
            <button className="button" onClick={() => void exportArch("pytorch")}><Icon name="download" /> Export PyTorch</button>
          </div>
          <ErrorList errors={errors} />
        </div>}</Loaded>}
      </Panel>
    </div> : null}
    {tab === "checkpoints" ? <div className="registry-workspace">
      <Panel title="Registered checkpoints" meta={`${checkpoints.length} SHOWN · /v1/models`}>
        <Loaded poll={models} label="checkpoints" isEmpty={() => checkpoints.length === 0} empty={needle ? "No checkpoints match this search." : "No model checkpoints registered."}>{() => <div className="table-wrap"><table aria-label="Registered checkpoints"><thead><tr><th>MODEL</th><th>KIND</th><th>VERSION</th><th>SHA-256</th><th>INTEGRITY</th><th /></tr></thead><tbody>
          {checkpoints.map((item) => { const integrity = integrityLabel(item); const key = `${item.model_id}@${item.version}`
            return <tr key={key} className={inspection && `${inspection.model_id}@${inspection.version}` === key ? "selected-row" : ""}><td className="mono">{item.model_id}</td><td>{item.kind}</td><td className="mono">{item.version}</td><td><code>{item.sha256.slice(0, 12)}</code></td>
              <td><Status tone={integrity.tone}>{integrity.text}</Status></td><td><button className="button compact" disabled={inspecting === key} onClick={() => void inspect(item)}>{inspecting === key ? "Inspecting…" : "Inspect"}</button></td></tr> })}
        </tbody></table></div>}</Loaded>
        <ErrorList errors={errors} />
      </Panel>
      <Panel title="Checkpoint inspection" meta={inspection ? `${inspection.tensor_count} TENSORS` : "NONE"}>
        {!inspection ? <EmptyState icon="registry" title="Choose Inspect on a checkpoint"><p>Lists tensors and the embedded metadata block, after re-verifying the SHA-256.</p></EmptyState> : <div className="registry-detail">
          {([["Model", `${inspection.model_id} v${inspection.version}`], ["Kind", inspection.kind], ["SHA-256", inspection.sha256], ["Tensors", formatCount(inspection.tensor_count)], ["Parameters", formatCount(inspection.parameter_count)], ["Top-level keys", inspection.top_level_keys.join(", ")]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
          {inspection.checkpoint_metadata ? <details><summary>Checkpoint metadata</summary><pre className="raw-json">{JSON.stringify(inspection.checkpoint_metadata, null, 1)}</pre></details> : <p className="panel-note">No metadata block in this checkpoint.</p>}
          <div className="table-wrap tensor-table"><table aria-label="Checkpoint tensors"><thead><tr><th>TENSOR</th><th>SHAPE</th><th>DTYPE</th></tr></thead><tbody>
            {inspection.tensors.map((tensor) => <tr key={tensor.name}><td><code>{tensor.name}</code></td><td className="mono">[{tensor.shape.join(", ")}]</td><td>{tensor.dtype}</td></tr>)}</tbody></table></div>
        </div>}
      </Panel>
    </div> : null}
    {tab === "deployments" ? <Deployments architectures={items(architectures.data)} models={items(models.data)} /> : null}
  </div>
}
