"use client"
import { useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { apiBase, describeFailure, request } from "../lib/api"
import type { ArchitectureItem, DeploymentItem, ModelItem, PredictionResult } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { ErrorList, Loaded, Notice, Panel, shortId, Status } from "../studio/ui"

/** Label shown next to every deployment and prediction: weights are never presented as trained unless they are. */
export function weightsBadge(item: Pick<DeploymentItem, "trained" | "model">): { text: string; tone: "teal" | "amber" } {
  return item.trained && item.model ? { text: `CHECKPOINT ${item.model.model_id}@${item.model.version}`, tone: "teal" } : { text: "UNTRAINED WEIGHTS", tone: "amber" }
}

export function curlExample(item: Pick<DeploymentItem, "predict_path">): string {
  return `curl -s -X POST ${apiBase}${item.predict_path} -H "x-api-key: $ARCHAI_API_KEY" -H "content-type: application/json" -d '{"input": "random", "batch_size": 1, "seed": 0}'`
}

export function Deployments({ architectures, models }: { architectures: ArchitectureItem[]; models: ModelItem[] }) {
  const deployments = usePoll<{ items: DeploymentItem[] }>("/v1/deployments", 10_000, itemsResponse)
  const [name, setName] = useState("")
  const [archId, setArchId] = useState("")
  const [model, setModel] = useState("")
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [notice, setNotice] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [inputKind, setInputKind] = useState<"random" | "zeros">("random")
  const [prediction, setPrediction] = useState<PredictionResult | null>(null)
  const verified = models.filter((item) => item.integrity_verified)
  const list = items(deployments.data)
  const current = list.find((item) => item.deployment_id === selected) ?? null

  const act = async <T,>(path: string, body?: unknown, method: "POST" | "DELETE" = "POST"): Promise<T | null> => {
    setBusy(true); setErrors([]); setNotice("")
    const result = await request<T>(path, { method, body, timeoutMs: 60_000 })
    setBusy(false)
    if (!result.ok) { setErrors([describeFailure(result)]); return null }
    deployments.refresh()
    return result.data
  }
  const create = async () => {
    const [modelId, version] = model ? model.split("@") : [null, null]
    const created = await act<DeploymentItem>("/v1/deployments", { name, architecture_id: archId, model_id: modelId, model_version: version })
    if (created) { setNotice(`Deployed ${created.name}.`); setName(""); setSelected(created.deployment_id); setPrediction(null) }
  }
  const predict = async (item: DeploymentItem) => {
    const result = await act<PredictionResult>(item.predict_path, { input: inputKind, batch_size: 1, seed: 0 })
    setPrediction(result)
  }

  return <div className="registry-workspace">
    <Panel title="Deployments" meta={`${list.length} · /v1/deployments`}>
      <p className="panel-note">Deployments serve a registered architecture from this API host. Weights come from a registered checkpoint whose SHA-256 is re-verified on load, or are untrained (seeded) and labelled as such.</p>
      <form className="access-forms" aria-label="Create deployment" onSubmit={(event) => { event.preventDefault(); void create() }}>
        <label className="field"><span>Name</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="cifar-candidate" required /></label>
        <label className="field"><span>Architecture</span><select value={archId} onChange={(event) => setArchId(event.target.value)} required><option value="">Select an architecture</option>{architectures.map((item) => <option key={item.architecture_id} value={item.architecture_id}>{item.architecture_id.slice(0, 16)} · {item.search_space}</option>)}</select></label>
        <label className="field"><span>Weights</span><select value={model} onChange={(event) => setModel(event.target.value)}><option value="">None — untrained (seeded) weights</option>{verified.map((item) => <option key={`${item.model_id}@${item.version}`} value={`${item.model_id}@${item.version}`}>{item.model_id}@{item.version} ({item.kind})</option>)}</select></label>
        <button className="button primary" type="submit" disabled={busy || !name.trim() || !archId}>Deploy</button>
      </form>
      <ErrorList errors={errors} /><Notice>{notice}</Notice>
      <Loaded poll={deployments} label="deployments" isEmpty={() => list.length === 0} empty="No deployments yet. Deploy a registered architecture above.">{() => <div className="table-wrap"><table aria-label="Deployments"><thead><tr><th>NAME</th><th>ARCHITECTURE</th><th>WEIGHTS</th><th>STATUS</th><th>REQUESTS</th><th>LAST LATENCY</th><th /></tr></thead><tbody>
        {list.map((item) => { const badge = weightsBadge(item)
          return <tr key={item.deployment_id} className={item.deployment_id === selected ? "selected-row" : ""}><td><button className="link-button" aria-pressed={item.deployment_id === selected} onClick={() => { setSelected(item.deployment_id); setPrediction(null) }}>{item.name}</button></td>
            <td className="mono">{shortId(item.architecture_id, 12)}</td><td><Status tone={badge.tone}>{badge.text}</Status></td>
            <td><Status tone={item.status === "active" ? "teal" : "gray"}>{item.status.toUpperCase()}</Status></td><td className="mono">{item.stats.request_count}</td>
            <td className="mono">{item.stats.last_latency_ms === null ? "—" : `${item.stats.last_latency_ms.toFixed(2)} ms`}</td>
            <td><span className="inspector-actions">{item.status === "active" ? <button className="button compact" disabled={busy} onClick={() => void act(`/v1/deployments/${item.deployment_id}/stop`)}>Stop</button> : <button className="button compact" disabled={busy} onClick={() => void act(`/v1/deployments/${item.deployment_id}/start`)}>Start</button>}
              <button className="button compact" disabled={busy} onClick={() => { if (window.confirm(`Delete deployment ${item.name}?`)) void act(`/v1/deployments/${item.deployment_id}`, undefined, "DELETE").then((done) => { if (done && selected === item.deployment_id) setSelected(null) }) }}>Delete</button></span></td></tr> })}
      </tbody></table></div>}</Loaded>
    </Panel>
    <Panel title="Test request" meta={current ? current.name.toUpperCase() : "NONE"}>
      {!current ? <p className="panel-note">Select a deployment to send a test request.</p> : <div className="registry-detail">
        {([["Endpoint", `POST ${current.predict_path}`], ["Input shape", `[batch, ${current.input_shape.join(", ")}]`], ["Weights", current.weights], ["Loaded in API process", current.loaded ? "yes" : "no (loads on first request)"]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
        <label className="field"><span>Test input</span><select value={inputKind} onChange={(event) => setInputKind(event.target.value as "random" | "zeros")}><option value="random">Random normal tensor (seed 0)</option><option value="zeros">All-zeros tensor</option></select></label>
        <button className="button primary" disabled={busy || current.status !== "active"} onClick={() => void predict(current)}>Send test request</button>
        {prediction ? <div className="registry-detail" aria-label="Prediction result">
          {([["Predicted class", prediction.predicted_class.join(", ")], ["Confidence", prediction.confidence.map((value) => value.toFixed(3)).join(", ")], ["Server latency", `${prediction.latency_ms.toFixed(2)} ms`], ["Input", prediction.input_source], ["Weights", prediction.weights]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
          {!prediction.trained ? <p className="panel-note">These weights are untrained, so the predicted class is not meaningful. Deploy a trained checkpoint for real predictions.</p> : null}
        </div> : null}
        <details><summary>Call it from a shell</summary><pre className="raw-json">{curlExample(current)}</pre></details>
      </div>}
    </Panel>
  </div>
}
