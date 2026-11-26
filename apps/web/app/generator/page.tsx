"use client"
import { useState } from "react"
import { Empty, Errors, PageHeader } from "../components/Shell"
import { postJson } from "../lib/api"

type Generated = { items: { architecture_id: string; architecture: { nodes: { id: string; op: string }[] } }[]; checkpoint: string }

export default function Generator() {
  const [count, setCount] = useState("4")
  const [seed, setSeed] = useState("0")
  const [result, setResult] = useState<Generated | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const submit = async () => {
    const outcome = await postJson<Generated>("/v1/architectures/generate", { count: Number(count), seed: Number(seed) })
    if (outcome.ok) { setResult(outcome.data); setErrors([]) } else { setResult(null); setErrors([`${outcome.status}: ${outcome.detail}`]) }
  }
  return <>
    <PageHeader eyebrow="GENERATOR" title="Candidate architecture generation" note="Requires a trained generator checkpoint configured on the API (ARCHAI_GENERATOR_CHECKPOINT); the API answers 503 otherwise." />
    <article className="panel">
      <div className="form-row"><label>Candidates<input value={count} onChange={(event) => setCount(event.target.value)} /></label><label>Seed<input value={seed} onChange={(event) => setSeed(event.target.value)} /></label><button onClick={() => void submit()}>Generate</button></div>
      <Errors errors={errors} />
      {result ? <ul>{result.items.map((item) => <li key={item.architecture_id}><code>{item.architecture_id.slice(0, 16)}</code><span>{item.architecture.nodes.map((node) => node.op).join(" → ")}</span></li>)}</ul> : <Empty>No candidates generated in this session.</Empty>}
    </article>
  </>
}
