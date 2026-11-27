"use client"
import { useState } from "react"
import { Empty, Errors, Loaded, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { fetchJson } from "../lib/api"
import { ci, separated, splitAblations } from "../lib/results"
import type { ArchitectureItem, CompareItem, ModelItem, ResearchResult } from "../lib/types"

const n = (value: number) => new Intl.NumberFormat().format(value)

export default function ModelComparison() {
  const architectures = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures", 15000)
  const models = usePoll<{ items: ModelItem[] }>("/v1/models", 15000)
  const suite = usePoll<ResearchResult>("/v1/research/results/nasbench201_cifar10_full_suite", 0)
  const [picked, setPicked] = useState<string[]>([])
  const [compared, setCompared] = useState<CompareItem[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const toggle = (id: string) => setPicked(picked.includes(id) ? picked.filter((value) => value !== id) : picked.length < 20 ? [...picked, id] : picked)
  const compare = async () => {
    const query = picked.map((id) => `ids=${encodeURIComponent(id)}`).join("&")
    const outcome = await fetchJson<{ items: CompareItem[] }>(`/v1/architectures/compare?${query}`)
    if (outcome.ok) { setCompared(outcome.data.items); setErrors([]) } else setErrors([`${outcome.status}: ${outcome.detail}`])
  }
  return <>
    <PageHeader eyebrow="MODEL COMPARISON" title="Compare architectures, checkpoints and policies" note="Architecture metrics are analytical (computed from the graph, not trained). Policy numbers are measured benchmark lookups with 95% bootstrap CIs over 10 seeds." />
    <div className="grid">
      <article className="panel wide"><h3>Search policies at a matched budget (100 queries)</h3>
        <Loaded poll={suite} isEmpty={(data) => !data.report} empty="No measured suite report available.">{(data) => {
          const { policies, ablations } = splitAblations(data)
          const random = data.report!.algorithms.random?.best_validation_accuracy
          const row = (name: string, ablation: boolean) => { const s = data.report!.algorithms[name]
            return <tr key={name}><td>{name}{ablation ? " (ablation)" : ""}</td><td className="num">{ci(s.best_validation_accuracy)}</td><td className="num">{ci(s.final_test_accuracy)}</td>
              <td className="num">{ci(data.regret?.[name], 3)}</td><td className="num">{ci(s.hypervolume_validation_params)}</td>
              <td>{name === "random" ? "baseline" : separated(s.best_validation_accuracy, random) ? (s.best_validation_accuracy.mean > (random?.mean ?? 0) ? "better than random" : "worse than random") : "overlaps random"}</td></tr> }
          return <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Best validation %</th><th>Test % of selected cell</th><th>Regret vs. oracle (pp)</th><th>Hypervolume</th><th>vs. random (CI overlap)</th></tr></thead>
            <tbody>{policies.map((name) => row(name, false))}{ablations.map((name) => row(name, true))}</tbody></table></div>
        }}</Loaded>
      </article>
      <article className="panel"><h3>Architectures (pick up to 20)</h3>
        <Loaded poll={architectures} isEmpty={(data) => items(data).length === 0} empty="No architectures registered. Register one in the Architecture Graph Explorer.">{(data) => <>
          <fieldset className="checks"><legend className="label">Registered architectures</legend>{items(data).map((item) => <label key={item.architecture_id}><input type="checkbox" checked={picked.includes(item.architecture_id)} onChange={() => toggle(item.architecture_id)} /><code>{item.architecture_id.slice(0, 12)}</code></label>)}</fieldset>
          <div className="form-row"><button disabled={picked.length < 2} onClick={() => void compare()}>Compare {picked.length} selected</button></div>
          {picked.length < 2 ? <p className="muted">Select at least two architectures.</p> : null}
        </>}</Loaded>
        <Errors errors={errors} />
      </article>
      <article className="panel"><h3>Checkpoints</h3>
        <Loaded poll={models} isEmpty={(data) => items(data).length === 0} empty="No checkpoints registered.">{(data) => <div className="table-scroll"><table><thead><tr><th>Model</th><th>Kind</th><th>Version</th><th>Integrity</th></tr></thead><tbody>
          {items(data).map((item) => <tr key={`${item.model_id}-${item.version}`}><td>{item.model_id}</td><td>{item.kind}</td><td>{item.version}</td><td>{item.integrity_verified ? "verified" : "MISMATCH or missing"}</td></tr>)}</tbody></table></div>}</Loaded>
        <p className="muted">Open a checkpoint in the Model Registry to inspect its tensors.</p>
      </article>
      <article className="panel wide"><h3>Architecture comparison</h3>
        {compared.length === 0 ? <Empty>Pick architectures and press Compare.</Empty> : <div className="table-scroll"><table><thead><tr><th>Architecture</th><th>Search space</th><th>Nodes</th><th>Edges</th><th>Parameters</th><th>FLOPs</th><th>Activation memory (bytes)</th></tr></thead><tbody>
          {compared.map((item) => { const fewest = Math.min(...compared.map((c) => c.analytical_metrics.parameters))
            return <tr key={item.architecture_id}><td><code>{item.architecture_id.slice(0, 12)}</code></td><td>{item.architecture.search_space ?? "—"}</td><td className="num">{item.architecture.nodes.length}</td><td className="num">{item.architecture.edges.length}</td>
              <td className="num">{n(item.analytical_metrics.parameters)}{item.analytical_metrics.parameters === fewest ? " (fewest)" : ""}</td><td className="num">{n(item.analytical_metrics.flops)}</td><td className="num">{n(item.analytical_metrics.activation_memory_bytes)}</td></tr> })}
        </tbody></table></div>}
      </article>
    </div>
  </>
}
