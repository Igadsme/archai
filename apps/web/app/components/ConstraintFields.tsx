"use client"
import type { ChangeEvent } from "react"
import type { ConstraintForm } from "../lib/forms"

type ConstraintHandler = (key: keyof ConstraintForm) => (event: ChangeEvent<HTMLInputElement>) => void

/** Optional budgets sent as `constraints`. Parameter and FLOP limits are raw counts; latency is in seconds. */
export function ConstraintFields({ form, onChange }: { form: ConstraintForm; onChange: ConstraintHandler }) {
  return <>
    <label className="field"><span>Max parameters <em>RAW COUNT</em></span><input inputMode="numeric" value={form.maxParameters} onChange={onChange("maxParameters")} placeholder="e.g. 800000" /></label>
    <label className="field"><span>Max FLOPs <em>RAW COUNT</em></span><input inputMode="numeric" value={form.maxFlops} onChange={onChange("maxFlops")} /></label>
    <label className="field"><span>Max latency (s) <em>NEEDS LATENCY MODEL</em></span><input inputMode="decimal" value={form.maxLatencyS} onChange={onChange("maxLatencyS")} /></label>
    <label className="field"><span>Allowed ops <em>COMMA-SEPARATED</em></span><input value={form.allowedOps} onChange={onChange("allowedOps")} placeholder="conv3x3, skip, avg_pool3x3" /></label>
  </>
}
