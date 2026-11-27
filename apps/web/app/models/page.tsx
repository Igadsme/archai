"use client"
import { useState } from "react"
import { Empty, Errors, Loaded, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { fetchJson } from "../lib/api"
import type { ModelInspection, ModelItem } from "../lib/types"

export default function ModelRegistry() {
  const models = usePoll<{ items: ModelItem[] }>("/v1/models", 10000)
  const [inspection, setInspection] = useState<ModelInspection | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const inspect = async (item: ModelItem) => {
    const outcome = await fetchJson<ModelInspection>(`/v1/models/${encodeURIComponent(item.model_id)}/inspect?version=${encodeURIComponent(item.version)}`)
    if (outcome.ok) { setInspection(outcome.data); setErrors([]) } else { setInspection(null); setErrors([`Inspection failed — ${outcome.status}: ${outcome.detail}`]) }
  }
  return <>
    <PageHeader eyebrow="MODEL REGISTRY" title="Checksum-backed checkpoints" note="Integrity is re-verified against the registered SHA-256 on every read; inspection refuses a file whose checksum no longer matches." />
    <article className="panel"><h3>Registered checkpoints</h3>
      <Loaded poll={models} isEmpty={(data) => items(data).length === 0} empty="No model checkpoints registered.">{(data) => <div className="table-scroll"><table><thead><tr><th>Model</th><th>Kind</th><th>Version</th><th>SHA-256</th><th>Integrity</th><th></th></tr></thead><tbody>
        {items(data).map((item) => <tr key={`${item.model_id}-${item.version}`}><td>{item.model_id}</td><td>{item.kind}</td><td>{item.version}</td><td><code>{item.sha256.slice(0, 12)}</code></td>
          <td>{item.integrity_verified === undefined ? "—" : item.integrity_verified ? "verified" : "MISMATCH or missing"}</td>
          <td><button onClick={() => void inspect(item)}>Inspect</button></td></tr>)}</tbody></table></div>}</Loaded>
      <Errors errors={errors} />
    </article>
    <article className="panel" style={{ marginTop: 12 }}><h3>Checkpoint inspection</h3>
      {!inspection ? <Empty>Choose Inspect on a checkpoint to list its tensors and metadata.</Empty> : <>
        <p className="muted">{inspection.model_id} v{inspection.version} · {inspection.tensor_count} tensors · {new Intl.NumberFormat().format(inspection.parameter_count)} parameters · keys: {inspection.top_level_keys.join(", ")}</p>
        {inspection.checkpoint_metadata ? <pre className="readme">{JSON.stringify(inspection.checkpoint_metadata, null, 1)}</pre> : <p className="muted">No metadata block in this checkpoint.</p>}
        <div className="table-scroll"><table><thead><tr><th>Tensor</th><th>Shape</th><th>dtype</th></tr></thead><tbody>
          {inspection.tensors.map((tensor) => <tr key={tensor.name}><td><code>{tensor.name}</code></td><td className="num">[{tensor.shape.join(", ")}]</td><td>{tensor.dtype}</td></tr>)}</tbody></table></div>
      </>}
    </article>
  </>
}
