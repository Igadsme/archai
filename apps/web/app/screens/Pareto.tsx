"use client"
import { useEffect, useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { downloadJson } from "../lib/api"
import { historyPoints, hypervolume, paretoFront } from "../lib/pareto"
import { jobResult } from "../lib/results"
import type { HistoryStep, JobDetail, ParetoPoint, ResearchResult, SearchItem } from "../lib/types"
import { itemsResponse } from "../lib/validators"
import { ScatterChart, type ScatterSeries } from "../studio/charts"
import { useGo, useQueryParam } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { EmptyState, Loaded, PageHeader, Panel, Status } from "../studio/ui"
import { SUITE } from "./Overview"

export const POLICY_COLORS = ["#5fc8c1", "#d3a85f", "#7ba4e8", "#df7b78", "#b59be8", "#8fc39d", "#e0c97a", "#8fa3c2"]
type Session = SearchItem & { job?: JobDetail }
type Picked = { series: string; point: ParetoPoint }

export function Pareto() {
  const go = useGo()
  const requested = useQueryParam("session")
  const suite = usePoll<ResearchResult>(`/v1/research/results/${SUITE}`, 0)
  const searches = usePoll<{ items: Session[] }>("/v1/searches", 10_000, itemsResponse)
  const [seed, setSeed] = useState("0")
  const [shown, setShown] = useState<string[]>(["multi_objective", "random", "bayesian"])
  const [sessionId, setSessionId] = useState("")
  const [picked, setPicked] = useState<Picked | null>(null)
  useEffect(() => { if (requested) setSessionId(requested) }, [requested])

  const pareto = suite.data?.pareto
  const policies = pareto ? Object.keys(pareto.policies) : []
  const seeds = pareto ? Object.keys(pareto.policies[policies[0]] ?? {}) : []
  const reference = (pareto?.hypervolume_reference ?? [0, 1.6]) as [number, number]
  const oracle = pareto?.full_space_front_trial_seed_for_seed0 ?? []
  const fronts = shown.filter((name) => pareto?.policies[name]?.[seed])
  const series: ScatterSeries[] = pareto ? [
    { label: "Full-space front (oracle, seed-0 trial)", kind: "reference", color: "#5b6b86", points: oracle.map((point) => ({ id: String(point.index), x: point.params_m, y: point.validation_accuracy, label: `cell ${point.index}` })) },
    ...fronts.map((name) => ({ label: `${name} · seed ${seed}`, kind: "front" as const, color: POLICY_COLORS[policies.indexOf(name) % POLICY_COLORS.length], points: pareto.policies[name][seed].front.map((point) => ({ id: String(point.index), x: point.params_m, y: point.validation_accuracy, label: `cell ${point.index}` })) })),
  ] : []
  const findPoint = (label: string, id: string): ParetoPoint | undefined => {
    if (label.startsWith("Full-space")) return oracle.find((point) => String(point.index) === id)
    const name = label.split(" · ")[0]
    return pareto?.policies[name]?.[seed]?.front.find((point) => String(point.index) === id)
  }
  const defaultPick = fronts[0] && pareto ? { series: `${fronts[0]} · seed ${seed}`, point: [...pareto.policies[fronts[0]][seed].front].sort((a, b) => b.validation_accuracy - a.validation_accuracy)[0] } : null
  const current = picked ?? defaultPick
  const session = items(searches.data).find((item) => item.search_id === sessionId)
  const sessionPoints = historyPoints(jobResult<{ history?: HistoryStep[] }>(session?.job)?.history ?? [])
  const sessionFront = paretoFront(sessionPoints)
  const tableRows = fronts.flatMap((name) => pareto!.policies[name][seed].front.map((point) => ({ name, point }))).sort((a, b) => a.point.params_m - b.point.params_m)

  return <div className="page">
    <PageHeader eyebrow={`PARETO / ${SUITE.toUpperCase()}`} title="Pareto optimization explorer" description="Maximize NATS-Bench cifar10-valid validation accuracy, minimize parameters (M). Evidence: benchmark_lookup from the committed suite (budget 100, 10 seeds).">
      <Status tone="teal">MEASURED · BENCHMARK_LOOKUP</Status>
      <button className="button" disabled={!pareto} onClick={() => pareto && downloadJson(`archai-pareto-seed${seed}.json`, { exported_at: new Date().toISOString(), source: `/v1/research/results/${SUITE}`, evidence_type: pareto.evidence_type, objectives: pareto.objectives, hypervolume_reference: pareto.hypervolume_reference, seed, fronts: Object.fromEntries(fronts.map((name) => [name, pareto.policies[name][seed]])) })}><Icon name="download" /> Export fronts</button>
    </PageHeader>
    <div className="analysis-constraints"><span>OBJECTIVES</span><code>max {pareto?.objectives?.maximize ?? "validation_accuracy"}</code><code>min {pareto?.objectives?.minimize ?? "params_m"}</code><span>HV REFERENCE</span><code>({reference[0]} %, {reference[1]} M)</code><span>SEED</span>
      <select aria-label="Seed" value={seed} onChange={(event) => { setSeed(event.target.value); setPicked(null) }}>{seeds.map((value) => <option key={value}>{value}</option>)}</select></div>
    <div className="pareto-layout">
      <Panel title="Accuracy / parameters frontier" meta={pareto ? `${fronts.length} POLICIES · SEED ${seed}` : "SUITE"}
        actions={policies.length ? <fieldset className="policy-toggles"><legend className="sr-only">Policies shown</legend>{policies.map((name, index) => <label key={name}><input type="checkbox" checked={shown.includes(name)} onChange={(event) => { setShown(event.target.checked ? [...shown, name] : shown.filter((value) => value !== name)); setPicked(null) }} /><i style={{ background: POLICY_COLORS[index % POLICY_COLORS.length] }} />{name}</label>)}</fieldset> : undefined}>
        <Loaded poll={suite} label="measured suite" isEmpty={(data) => !data.pareto} empty="This result set has no pareto.json.">{() =>
          <ScatterChart label={`Pareto fronts per policy for seed ${seed}`} series={series} xLabel="PARAMETERS (M) — LOWER IS BETTER" yLabel="VALIDATION ACCURACY (%)"
            selected={current ? `${current.series}:${current.point.index}` : null}
            onSelect={(point, item) => { const found = findPoint(item.label, point.id); if (found) setPicked({ series: item.label, point: found }) }} />}</Loaded>
      </Panel>
      <Panel title="Candidate detail" meta={current ? current.series.toUpperCase() : "NONE"}>
        {current ? <div className="pareto-detail">
          <span className="candidate-chip">CELL {current.point.index}</span>
          <h2>{current.point.validation_accuracy.toFixed(2)}%</h2><p className="muted">validation accuracy (selection metric)</p>
          {([["Parameters", `${current.point.params_m.toFixed(3)} M`], ["FLOPs", current.point.flops_m !== undefined ? `${current.point.flops_m.toFixed(2)} M` : "not reported"], ["Series", current.series], ["Evidence", pareto?.evidence_type ?? "benchmark_lookup"]] as const).map(([label, value]) => <div className="property" key={label}><span>{label}</span><code>{value}</code></div>)}
          {current.point.architecture_string ? <><h3 className="detail-label">CELL STRING</h3><code className="arch-string block">{current.point.architecture_string}</code></> : null}
          <p className="panel-note">Test accuracy is not used for selection; see Benchmark comparison for held-out results.</p>
          <button className="button" onClick={() => go("benchmarks")}>Open benchmark comparison</button>
        </div> : <EmptyState icon="pareto" title="Select a point on the frontier" />}
      </Panel>
      <Panel title="Pareto set" meta={`${tableRows.length} NON-DOMINATED POINTS · SEED ${seed}`}>
        {tableRows.length ? <div className="table-wrap"><table aria-label="Pareto set"><thead><tr><th>POLICY</th><th>CELL</th><th>VALIDATION %</th><th>PARAMS (M)</th><th>FLOPS (M)</th><th>FRONT HV</th></tr></thead><tbody>
          {tableRows.map(({ name, point }) => <tr key={`${name}-${point.index}`} className={current?.point.index === point.index && current.series.startsWith(name) ? "selected-row" : ""} onClick={() => setPicked({ series: `${name} · seed ${seed}`, point })}>
            <td><i className="legend-dot" style={{ background: POLICY_COLORS[policies.indexOf(name) % POLICY_COLORS.length] }} />{name}</td><td className="mono">{point.index}</td><td className="mono">{point.validation_accuracy.toFixed(2)}</td><td className="mono">{point.params_m.toFixed(3)}</td><td className="mono">{point.flops_m?.toFixed(2) ?? "—"}</td><td className="mono">{pareto!.policies[name][seed].hypervolume?.toFixed(2) ?? "—"}</td></tr>)}
        </tbody></table></div> : <div className="empty-inline">Enable at least one policy to list its front.</div>}
        {pareto ? <div className="table-wrap"><table aria-label="Hypervolume by policy"><thead><tr><th>POLICY</th><th>FRONT SIZE (SEED {seed})</th><th>HV (SEED {seed})</th><th>HV MEAN [95% CI], ALL SEEDS</th></tr></thead><tbody>
          {policies.map((name) => { const run = pareto.policies[name][seed]; const summary = suite.data?.report?.algorithms[name]?.hypervolume_validation_params
            return <tr key={name}><td>{name}</td><td className="mono">{run?.front.length ?? "—"}</td><td className="mono">{run?.hypervolume?.toFixed(2) ?? "—"}</td><td className="mono">{summary ? `${summary.mean.toFixed(2)} [${summary.ci_low.toFixed(2)}, ${summary.ci_high.toFixed(2)}]` : "—"}</td></tr> })}
        </tbody></table></div> : null}
      </Panel>
      <Panel title="Live search session" meta={session ? `${session.algorithm.toUpperCase()} · ${session.status?.toUpperCase()}` : "API SESSIONS"} className="live-front">
        <Loaded poll={searches} label="search sessions" isEmpty={(data) => data.items.length === 0} empty="No search sessions yet. Launch one in the Autonomous Search Laboratory.">{(data) => <>
          <label className="field inline-field"><span>Session</span><select value={sessionId} onChange={(event) => setSessionId(event.target.value)}><option value="">Choose a session</option>
            {data.items.map((item) => <option key={item.search_id} value={item.search_id}>{item.algorithm} · seed {item.seed} · {item.status} · {item.search_id.slice(0, 8)}</option>)}</select></label>
          {!sessionId ? null : sessionPoints.length === 0 ? <div className="empty-inline">This session has no evaluated points with a parameter cost yet (status: {session?.status}).</div> : <>
            <ScatterChart label="Evaluated cells and their Pareto front for the selected session" xLabel="PARAMETERS (M)" yLabel="VALIDATION ACCURACY (%)"
              series={[{ label: "Evaluated cells", kind: "cloud", color: "#3d6a80", points: sessionPoints.map((point, index) => ({ id: `${index}`, x: point.params_m, y: point.validation_accuracy, label: `cell ${point.index}` })) },
                { label: "Session front", kind: "front", color: "#5fc8c1", points: sessionFront.map((point) => ({ id: `f${point.index}`, x: point.params_m, y: point.validation_accuracy, label: `cell ${point.index}` })) }]} />
            <p className="panel-note">{sessionPoints.length} evaluated · front size {sessionFront.length} · hypervolume {hypervolume(sessionPoints, reference).toFixed(2)} (computed in the browser from the worker history, same formula as archai_benchmark.hypervolume_2d)</p>
          </>}
        </>}</Loaded>
      </Panel>
    </div>
  </div>
}
