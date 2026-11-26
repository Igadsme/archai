"use client"
import { useState } from "react"
import { Empty, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import type { ExperimentItem } from "../lib/types"

export default function Experiments() {
  const [evidence, setEvidence] = useState("all")
  const experiments = items(usePoll<{ items: ExperimentItem[] }>("/v1/experiments").data)
  const shown = experiments.filter((item) => evidence === "all" || item.evidence_type === evidence)
  return <>
    <PageHeader eyebrow="EXPERIMENTS" title="Provenance-backed evidence" note="Predicted, benchmark-lookup and measured-training evidence are recorded separately and never mixed." />
    <article className="panel">
      <div className="form-row"><label>Evidence type<select value={evidence} onChange={(event) => setEvidence(event.target.value)}><option>all</option><option>predicted</option><option>benchmark_lookup</option><option>measured_training</option></select></label></div>
      {shown.length === 0 ? <Empty>No experiments match.</Empty> : <table><thead><tr><th>Experiment</th><th>Evidence</th><th>Status</th><th>Seed</th><th>Metrics</th></tr></thead><tbody>{shown.map((item) => <tr key={item.experiment_id}><td><code>{item.experiment_id.slice(0, 10)}</code></td><td>{item.evidence_type}</td><td>{item.status}</td><td>{item.provenance?.seed ?? "—"}</td><td>{Object.entries(item.metrics).map(([key, value]) => `${key}=${value}`).join(", ") || "—"}</td></tr>)}</tbody></table>}
    </article>
  </>
}
