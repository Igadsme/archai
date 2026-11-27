"use client"
import { useRef, useState } from "react"
import { ConstraintFields } from "../components/ConstraintFields"
import { SelectedProjectLabel, useSelectedProject } from "../components/ProjectPicker"
import { request, type ApiError } from "../lib/api"
import { buildConstraints, defaultConstraintForm, type ConstraintForm } from "../lib/forms"
import type { ArchitectureDetail, FullArchitecture } from "../lib/types"
import { architectureDetailResponse, generateResponse } from "../lib/validators"
import { useGo } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { MiniGraph } from "../studio/MiniGraph"
import { ErrorList, formatBytes, formatCompact, PageHeader, Panel, shortId, Status, Unavailable } from "../studio/ui"

/** Operations archai_generator can sample (archai_generator.model.GENERATABLE_OPS). */
export const GENERATABLE_OPS = [
  { op: "conv3x3", label: "Conv 3×3", detail: "Conv + norm + act" },
  { op: "conv1x1", label: "Conv 1×1", detail: "Pointwise mixing" },
  { op: "avg_pool3x3", label: "Avg pool 3×3", detail: "Stride 1, same size" },
  { op: "skip", label: "Skip", detail: "Identity path" },
] as const

type Generated = { items: { architecture_id: string; architecture: FullArchitecture }[]; count: number; checkpoint: string; metadata: Record<string, unknown>; attempts?: number; rejected?: number }
type Form = { count: string; seed: string; channels: string; height: string; width: string; classes: string } & ConstraintForm
const defaultForm: Form = { count: "4", seed: "0", channels: "3", height: "32", width: "32", classes: "10", ...defaultConstraintForm }

export function buildGenerateRequest(form: Form, ops: string[], projectId?: string): { ok: true; value: Record<string, unknown> } | { ok: false; errors: string[] } {
  const errors: string[] = []
  const int = (raw: string, label: string, min: number, max: number) => {
    const value = /^\d+$/.test(raw.trim()) ? Number(raw.trim()) : NaN
    if (!Number.isInteger(value) || value < min || value > max) errors.push(`${label} must be an integer in [${min}, ${max}]`)
    return value
  }
  const count = int(form.count, "candidates", 1, 64)
  const seed = int(form.seed, "seed", 0, 2 ** 31 - 1)
  const channels = int(form.channels, "input channels", 1, 4096)
  const height = int(form.height, "input height", 1, 4096)
  const width = int(form.width, "input width", 1, 4096)
  const classes = int(form.classes, "output classes", 2, 10000)
  if (!ops.length) errors.push("select at least one operation")
  const allSelected = ops.length === GENERATABLE_OPS.length
  const constraints = buildConstraints({ ...form, allowedOps: form.allowedOps || (allSelected ? "" : ops.join(",")) })
  if (!constraints.ok) errors.push(...constraints.errors)
  if (errors.length) return { ok: false, errors }
  const value: Record<string, unknown> = { count, seed, input_spec: { channels, height, width }, output_classes: classes }
  if (projectId) value.project_id = projectId
  if (constraints.ok && constraints.value) value.constraints = constraints.value
  return { ok: true, value }
}

type Check = { detail?: ArchitectureDetail; error?: string; saved?: "saving" | "saved" | string }

export function Generator() {
  const go = useGo()
  const { projectId } = useSelectedProject()
  const [form, setForm] = useState<Form>(defaultForm)
  const [ops, setOps] = useState<string[]>(GENERATABLE_OPS.map((item) => item.op))
  const [result, setResult] = useState<Generated | null>(null)
  const [failure, setFailure] = useState<ApiError | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(0)
  const [checks, setChecks] = useState<Record<string, Check>>({})
  const inflight = useRef<AbortController | null>(null)
  const set = (key: keyof Form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value })

  const validate = async (item: Generated["items"][number]) => {
    setChecks((current) => ({ ...current, [item.architecture_id]: { ...current[item.architecture_id] } }))
    const outcome = await request<ArchitectureDetail>("/v1/architectures/validate", { method: "POST", body: item.architecture, validate: architectureDetailResponse })
    setChecks((current) => ({ ...current, [item.architecture_id]: { ...current[item.architecture_id], ...(outcome.ok ? { detail: outcome.data } : { error: outcome.error.message }) } }))
  }

  const generate = async () => {
    const built = buildGenerateRequest(form, ops, projectId || undefined)
    if (!built.ok) { setErrors(built.errors); return }
    inflight.current?.abort()
    const controller = new AbortController()
    inflight.current = controller
    setBusy(true); setErrors([]); setFailure(null)
    const outcome = await request<Generated>("/v1/architectures/generate", { method: "POST", body: built.value, signal: controller.signal, timeoutMs: 120_000, validate: generateResponse })
    if (controller.signal.aborted) return
    setBusy(false)
    if (!outcome.ok) { setResult(null); setFailure(outcome.error); return }
    setResult(outcome.data); setSelected(0); setChecks({})
    outcome.data.items.forEach((item) => void validate(item))
  }
  const cancel = () => { inflight.current?.abort(); setBusy(false) }
  const reset = () => { cancel(); setForm(defaultForm); setOps(GENERATABLE_OPS.map((item) => item.op)); setResult(null); setFailure(null); setErrors([]) }

  const save = async (item: Generated["items"][number]) => {
    setChecks((current) => ({ ...current, [item.architecture_id]: { ...current[item.architecture_id], saved: "saving" } }))
    const outcome = await request<ArchitectureDetail>("/v1/architectures", { method: "POST", body: item.architecture, validate: architectureDetailResponse })
    setChecks((current) => ({ ...current, [item.architecture_id]: { ...current[item.architecture_id], saved: outcome.ok ? "saved" : `failed — ${outcome.error.message}` } }))
  }

  const current = result?.items[selected]
  const check = current ? checks[current.architecture_id] : undefined
  const meta = busy ? "SAMPLING…" : failure ? (failure.unavailable ? "GENERATOR UNAVAILABLE" : "REQUEST FAILED") : result ? `${result.count} CANDIDATES` : "AWAITING CONFIGURATION"
  return <div className="page">
    <PageHeader eyebrow="DESIGN SPACE / CONFIGURATION" title="Architecture generator" description="Sample candidates from the trained ArchAI-V1 generator checkpoint. Every candidate is validated by the API before it is shown.">
      <button className="button" onClick={reset}>Reset</button>
      {busy ? <button className="button" onClick={cancel}><Icon name="close" /> Cancel</button> : null}
      <button className="button primary" onClick={() => void generate()} disabled={busy}><Icon name="play" /> Generate candidates</button>
    </PageHeader>
    <div className="generator-layout">
      <div className="config-column">
        <Panel title="01 / Operator vocabulary" meta="ALLOWED OPS">
          <div className="form-body">
            <p className="panel-note">Operations the generator may place. Selecting all sends no op constraint; a subset is sent as <code>constraints.allowed_ops</code>.</p>
            <div className="choice-grid">
              {GENERATABLE_OPS.map((item) => <button key={item.op} type="button" aria-pressed={ops.includes(item.op)} className={`choice ${ops.includes(item.op) ? "selected" : ""}`}
                onClick={() => setOps((value) => value.includes(item.op) ? value.filter((op) => op !== item.op) : [...value, item.op])}>
                <i>{ops.includes(item.op) && <Icon name="check" size={12} />}</i><span>{item.label}<small>{item.detail}</small></span></button>)}
            </div>
          </div>
        </Panel>
        <Panel title="02 / Sampling & tensor contract" meta="REQUEST">
          <div className="form-body form-grid">
            <label className="field"><span>Candidates <em>{form.count || "—"} / 64</em></span><input inputMode="numeric" value={form.count} onChange={set("count")} /></label>
            <label className="field"><span>Seed <em>REPRODUCIBLE</em></span><input inputMode="numeric" value={form.seed} onChange={set("seed")} /></label>
            <label className="field"><span>Input channels</span><input inputMode="numeric" value={form.channels} onChange={set("channels")} /></label>
            <label className="field"><span>Output classes</span><input inputMode="numeric" value={form.classes} onChange={set("classes")} /></label>
            <label className="field"><span>Input height</span><input inputMode="numeric" value={form.height} onChange={set("height")} /></label>
            <label className="field"><span>Input width</span><input inputMode="numeric" value={form.width} onChange={set("width")} /></label>
          </div>
        </Panel>
        <Panel title="03 / Objective envelope" meta="CONSTRAINTS">
          <div className="form-body form-grid"><ConstraintFields form={form} onChange={set} /></div>
          <div className="form-body project-line"><SelectedProjectLabel /></div>
        </Panel>
        <ErrorList errors={errors} />
      </div>
      <Panel title="Generation preview" meta={meta} className="preview-panel">
        {busy ? <div className="empty-state"><div className="empty-grid spinning"><Icon name="generator" size={34} /></div><h3>Sampling from the checkpoint…</h3><p>The API loads the checkpoint, samples, filters by constraints and validates each graph.</p></div>
          : failure ? (failure.unavailable
            ? <div className="empty-state"><Unavailable feature="trained generator" reason={failure.detail}>
                <p>The API answers 503 when <code>ARCHAI_GENERATOR_CHECKPOINT</code> is not set or the checkpoint cannot be loaded. No candidates are simulated.</p>
              </Unavailable></div>
            : <div className="error-state"><div><span>!</span><h3>Generation request failed</h3></div><p>{failure.message}</p>
                {failure.kind === "http" && failure.status === 422 ? <p>The checkpoint could not produce enough candidates inside the requested constraints. Relax the envelope or change the seed.</p> : null}
                <button className="button" onClick={() => void generate()}>Retry</button></div>)
          : result && current ? <div className="generated-state">
            <div className="candidate-strip" role="tablist" aria-label="Generated candidates">{result.items.map((item, index) => <button key={item.architecture_id} role="tab" aria-selected={index === selected} className={index === selected ? "active" : ""} onClick={() => setSelected(index)}>
              <code>{shortId(item.architecture_id)}</code><small>{item.architecture.nodes.length} nodes</small></button>)}</div>
            <div className="generated-id"><span>GENERATED CANDIDATE {selected + 1} / {result.count}</span><strong>{shortId(current.architecture_id, 16)}</strong>
              {check?.detail ? <Status>VALID GRAPH</Status> : check?.error ? <Status tone="red">INVALID</Status> : <Status tone="amber">VALIDATING</Status>}</div>
            <MiniGraph architecture={current.architecture} label={`Candidate ${shortId(current.architecture_id)}`} />
            <div className="stat-strip">
              <span><small>NODES / EDGES</small><b>{current.architecture.nodes.length} / {current.architecture.edges.length}</b></span>
              <span><small>PARAMS (ANALYTICAL)</small><b>{formatCompact(check?.detail?.analytical_metrics.parameters)}</b></span>
              <span><small>FLOPs (ANALYTICAL)</small><b>{formatCompact(check?.detail?.analytical_metrics.flops)}</b></span>
              <span><small>ACT. MEMORY</small><b>{formatBytes(check?.detail?.analytical_metrics.activation_memory_bytes)}</b></span>
            </div>
            <div className="validation-list">
              <div><Icon name={check?.detail ? "check" : "alert"} /><span>Schema and DAG validation (POST /v1/architectures/validate)</span><b>{check?.detail ? "PASS" : check?.error ? "FAIL" : "…"}</b></div>
              <div><Icon name={check?.detail?.hash === current.architecture_id ? "check" : "alert"} /><span>Canonical hash matches candidate id</span><b>{check?.detail ? (check.detail.hash === current.architecture_id ? "PASS" : "MISMATCH") : "…"}</b></div>
              <div><Icon name="database" /><span>Checkpoint</span><b className="mono">{result.checkpoint.split("/").pop()}</b></div>
              {typeof result.rejected === "number" ? <div><Icon name="filter" /><span>Rejected by constraints / attempts</span><b>{result.rejected} / {result.attempts ?? "—"}</b></div> : null}
            </div>
            {check?.error ? <ErrorList errors={[check.error]} /> : null}
            <div className="preview-actions">
              {check?.saved === "saved" ? <button className="button" onClick={() => go("explorer", { id: current.architecture_id })}>Open in explorer</button> : null}
              <button className="button primary" disabled={check?.saved === "saving" || check?.saved === "saved"} onClick={() => void save(current)}>
                {check?.saved === "saved" ? "Saved to registry" : check?.saved === "saving" ? "Saving…" : "Save to registry"}</button>
            </div>
            {check?.saved && check.saved.startsWith("failed") ? <ErrorList errors={[check.saved]} /> : null}
            <details className="raw-json"><summary>Checkpoint metadata</summary><pre>{JSON.stringify(result.metadata, null, 2)}</pre></details>
          </div>
          : <div className="empty-state"><div className="empty-grid"><Icon name="generator" size={34} /></div><h3>No candidate generated</h3><p>Configure the vocabulary, tensor contract and constraints, then sample candidates from the trained generator.</p><code>POST /v1/architectures/generate · seed {form.seed || "—"}</code></div>}
      </Panel>
    </div>
  </div>
}
