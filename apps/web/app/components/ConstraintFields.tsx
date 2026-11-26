"use client"
import type { ChangeEvent } from "react"
import type { ConstraintForm } from "../lib/forms"

type ConstraintHandler = (key: keyof ConstraintForm) => (event: ChangeEvent<HTMLInputElement>) => void

export function ConstraintFields({ form, onChange }: { form: ConstraintForm; onChange: ConstraintHandler }) {
  return <>
    <p className="muted">Optional budgets. Parameter and FLOP limits are raw counts (NATS-Bench 0.8M params is 800000). Latency is in seconds; generate rejects it when no latency model is available. Allowed ops are a comma-separated subset of the compiler and NAS-Bench-201 operations.</p>
    <label>Max parameters<input inputMode="numeric" value={form.maxParameters} onChange={onChange("maxParameters")} /></label>
    <label>Max FLOPs<input inputMode="numeric" value={form.maxFlops} onChange={onChange("maxFlops")} /></label>
    <label>Max latency (s)<input inputMode="decimal" value={form.maxLatencyS} onChange={onChange("maxLatencyS")} /></label>
    <label>Allowed ops<input value={form.allowedOps} onChange={onChange("allowedOps")} placeholder="nor_conv_3x3, skip_connect, none" /></label>
  </>
}
