"use client"
import Link from "next/link"
import { useState } from "react"
import { DagView } from "../components/DagView"
import { Empty, Errors, PageHeader, Unavailable } from "../components/Shell"
import { postJson } from "../lib/api"
import type { FullArchitecture } from "../lib/types"

type Generated = { items: { architecture_id: string; architecture: FullArchitecture }[]; checkpoint: string; metadata: Record<string, unknown> }

export default function ArchitectureGenerator() {
  const [form, setForm] = useState({ count: "4", seed: "0", channels: "3", height: "32", width: "32", classes: "10" })
  const [result, setResult] = useState<Generated | null>(null)
  const [selected, setSelected] = useState(0)
  const [errors, setErrors] = useState<string[]>([])
  const [saved, setSaved] = useState<Record<string, string>>({})
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value })
  const submit = async () => {
    const numbers = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, Number(value)]))
    if (Object.values(numbers).some((value) => !Number.isInteger(value) || value < 0)) { setErrors(["all fields must be non-negative integers"]); return }
    const outcome = await postJson<Generated>("/v1/architectures/generate", { count: numbers.count, seed: numbers.seed,
      input_spec: { channels: numbers.channels, height: numbers.height, width: numbers.width }, output_classes: numbers.classes })
    if (outcome.ok) { setResult(outcome.data); setSelected(0); setErrors([]) } else { setResult(null); setErrors([`${outcome.status}: ${outcome.detail}`]) }
  }
  const save = async (architecture: FullArchitecture, id: string) => {
    const outcome = await postJson<{ hash: string }>("/v1/architectures", architecture)
    setSaved({ ...saved, [id]: outcome.ok ? "saved" : `failed: ${outcome.detail}` })
  }
  const current = result?.items[selected]
  return <>
    <PageHeader eyebrow="ARCHITECTURE GENERATOR" title="Sample candidates from a trained generator"
      note="The API samples from the checkpoint in ARCHAI_GENERATOR_CHECKPOINT and answers 503 when none is configured. Every candidate is validated before it is returned." />
    <div className="grid">
      <article className="panel"><h3>Generate</h3>
        <div className="form two-col">
          <label>Candidates (1–64)<input inputMode="numeric" value={form.count} onChange={set("count")} /></label>
          <label>Seed<input inputMode="numeric" value={form.seed} onChange={set("seed")} /></label>
          <label>Input channels<input inputMode="numeric" value={form.channels} onChange={set("channels")} /></label>
          <label>Output classes<input inputMode="numeric" value={form.classes} onChange={set("classes")} /></label>
          <label>Input height<input inputMode="numeric" value={form.height} onChange={set("height")} /></label>
          <label>Input width<input inputMode="numeric" value={form.width} onChange={set("width")} /></label>
        </div>
        <button onClick={() => void submit()}>Generate candidates</button>
        <Errors errors={errors} />
        <Unavailable feature="constraint-conditioned generation in the Studio" reason="The parameter-budget and accuracy conditions exist only in the offline NAS-Bench-201 generator (scripts/train_generator_nb201.py), and at smoke scale the budget condition is not met better than random. The API generator has no constraint inputs." />
      </article>
      <article className="panel"><h3>Candidates</h3>
        {result ? <><p className="muted">Checkpoint: <code>{result.checkpoint}</code></p>
          <ul>{result.items.map((item, index) => <li key={item.architecture_id}>
            <button className="link-button" aria-pressed={index === selected} onClick={() => setSelected(index)}><code>{item.architecture_id.slice(0, 12)}</code></button>
            <span>{item.architecture.nodes.length} nodes · {saved[item.architecture_id] ?? <button className="link-button" onClick={() => void save(item.architecture, item.architecture_id)}>save to registry</button>}</span></li>)}</ul></>
          : <Empty>No candidates generated in this session.</Empty>}
      </article>
    </div>
    {current ? <article className="panel"><h3>Candidate graph <code>{current.architecture_id.slice(0, 12)}</code></h3><DagView architecture={current.architecture} />
      <p className="muted">Saved candidates can be exported as PyTorch from the <Link href="/explorer">Architecture Graph Explorer</Link>.</p></article> : null}
  </>
}
