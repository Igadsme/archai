"use client"
import { useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { describeFailure, fetchJson } from "../lib/api"
import { buildLeaderboard } from "../lib/leaderboard"
import { ci, separated, splitAblations } from "../lib/results"
import type { ArchitectureItem, CompareItem, ExperimentItem, ResearchResult } from "../lib/types"
import { compareResponse, itemsResponse } from "../lib/validators"
import { useGo } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { EmptyState, ErrorList, formatBytes, formatCompact, formatCount, Loaded, PageHeader, Panel, Status } from "../studio/ui"
import { SUITE } from "./Overview"

type ResultSet = { name: string; files: string[] }
const METRICS = [["parameters", "Parameters", formatCompact], ["flops", "FLOPs", formatCompact], ["activation_memory_bytes", "Activation memory", formatBytes]] as const
export const COMPARE_COLORS = ["#5fc8c1", "#7ba4e8", "#d3a85f", "#df7b78", "#b59be8"]

/** Bar widths relative to the largest value in each metric; the smallest value is marked best. */
export function normalizeMetrics(compared: CompareItem[]) {
  return METRICS.map(([key, label]) => {
    const values = compared.map((item) => item.analytical_metrics[key])
    const max = Math.max(...values, 1)
    const min = Math.min(...values)
    return { key, label, rows: compared.map((item) => ({ id: item.architecture_id, value: item.analytical_metrics[key], fraction: item.analytical_metrics[key] / max, best: item.analytical_metrics[key] === min })) }
  })
}

export function Benchmarks() {
  const go = useGo()
  const architectures = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures?limit=200", 15_000, itemsResponse)
  const suite = usePoll<ResearchResult>(`/v1/research/results/${SUITE}`, 0)
  const sets = usePoll<{ items: ResultSet[]; root_available: boolean }>("/v1/research/results", 0)
  const experiments = usePoll<{ items: ExperimentItem[] }>("/v1/experiments", 15_000, itemsResponse)
  const [picked, setPicked] = useState<string[]>([])
  const [compared, setCompared] = useState<CompareItem[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [setName, setSetName] = useState(SUITE)
  const detail = usePoll<ResearchResult>(setName ? `/v1/research/results/${encodeURIComponent(setName)}` : null, 0)
  const leaderboard = buildLeaderboard(items(experiments.data))
  const toggle = (id: string) => setPicked(picked.includes(id) ? picked.filter((value) => value !== id) : picked.length < 5 ? [...picked, id] : picked)
  const compare = async () => {
    setBusy(true)
    const outcome = await fetchJson<{ items: CompareItem[] }>(`/v1/architectures/compare?${picked.map((id) => `ids=${encodeURIComponent(id)}`).join("&")}`, { validate: compareResponse })
    setBusy(false)
    if (outcome.ok) { setCompared(outcome.data.items); setErrors([]) } else setErrors([describeFailure(outcome)])
  }
  const color = (id: string) => COMPARE_COLORS[compared.findIndex((item) => item.architecture_id === id) % COMPARE_COLORS.length]

  return <div className="page">
    <PageHeader eyebrow="BENCHMARK COMPARISON" title="Benchmark comparison" description="Policy numbers are measured NATS-Bench lookups with 95% bootstrap CIs over 10 seeds. Architecture numbers are analytical (computed from the graph, not trained).">
      <Status tone="teal">MATCHED BUDGET {suite.data?.report?.matched_budget ?? suite.data?.experiment?.budget ?? "—"}</Status>
      <button className="button primary" disabled={picked.length < 2 || busy} onClick={() => void compare()}>{busy ? "Comparing…" : `Compare ${picked.length} selected`}</button>
    </PageHeader>
    <div className="benchmark-grid">
      <Panel title="Search policies at a matched budget" meta="BENCHMARK_LOOKUP · 95% CI" className="span-3">
        <Loaded poll={suite} label="measured suite" isEmpty={(data) => !data.report} empty="No measured suite report available.">{(data) => {
          const { policies, ablations } = splitAblations(data)
          const random = data.report!.algorithms.random?.best_validation_accuracy
          const row = (name: string, ablation: boolean) => { const s = data.report!.algorithms[name]
            const verdict = name === "random" ? "baseline" : separated(s.best_validation_accuracy, random) ? (s.best_validation_accuracy.mean > (random?.mean ?? 0) ? "better than random" : "worse than random") : "overlaps random"
            return <tr key={name}><td>{name}{ablation ? <span className="badge">ABLATION</span> : null}</td><td className="mono">{ci(s.best_validation_accuracy)}</td><td className="mono">{ci(s.final_test_accuracy)}</td>
              <td className="mono">{ci(data.regret?.[name], 3)}</td><td className="mono">{ci(s.hypervolume_validation_params)}</td><td><span className={`badge ${verdict === "better than random" ? "badge-pareto" : verdict === "baseline" ? "" : "badge-archived"}`}>{verdict.toUpperCase()}</span></td></tr> }
          return <div className="table-wrap"><table aria-label="Search policies at a matched budget"><thead><tr><th>POLICY</th><th>BEST VALIDATION %</th><th>TEST % OF SELECTED CELL</th><th>REGRET VS. ORACLE (PP)</th><th>HYPERVOLUME</th><th>VS. RANDOM (CI OVERLAP)</th></tr></thead>
            <tbody>{policies.map((name) => row(name, false))}{ablations.map((name) => row(name, true))}</tbody></table></div>
        }}</Loaded>
      </Panel>
      <Panel title="Registered architectures" meta={`${picked.length}/5 SELECTED`}>
        <Loaded poll={architectures} label="architectures" isEmpty={(data) => data.items.length === 0} empty="No architectures registered. Register one in the Neural Architecture Explorer.">{(data) => <div className="compare-list">
          <fieldset><legend className="sr-only">Registered architectures</legend>
            {data.items.map((item) => <label key={item.architecture_id}><input type="checkbox" checked={picked.includes(item.architecture_id)} onChange={() => toggle(item.architecture_id)} aria-label={`Select ${item.architecture_id.slice(0, 12)}`} />
              <i style={{ background: picked.includes(item.architecture_id) ? COMPARE_COLORS[picked.indexOf(item.architecture_id) % COMPARE_COLORS.length] : "#2c3a45" }} />
              <span><b className="mono">{item.architecture_id.slice(0, 12)}</b><small>{item.search_space} · {formatCompact(item.metrics.parameters)} params · {formatCompact(item.metrics.flops)} FLOPs</small></span></label>)}
          </fieldset>
          {picked.length < 2 ? <p className="panel-note">Select two to five architectures, then press Compare.</p> : null}
          <ErrorList errors={errors} />
        </div>}</Loaded>
      </Panel>
      <Panel title="Analytical comparison" meta={compared.length ? `${compared.length} ARCHITECTURES · ANALYTICAL` : "GET /v1/architectures/compare"} className="span-2">
        {compared.length === 0 ? <EmptyState icon="benchmarks" title="Pick architectures and press Compare" /> : <>
          <div className="radar-like metric-bars">{normalizeMetrics(compared).map((metric) => <div key={metric.key} className="metric-bar-group"><h3>{metric.label.toUpperCase()}</h3>
            {metric.rows.map((row) => <div className="metric-bar" key={row.id}><code>{row.id.slice(0, 8)}</code><span><i style={{ width: `${Math.max(2, row.fraction * 100)}%`, background: color(row.id) }} /></span><b>{metric.key === "activation_memory_bytes" ? formatBytes(row.value) : formatCompact(row.value)}{row.best ? " ★" : ""}</b></div>)}</div>)}</div>
          <div className="table-wrap"><table aria-label="Architecture comparison"><thead><tr><th>ARCHITECTURE</th><th>SEARCH SPACE</th><th>NODES</th><th>EDGES</th><th>PARAMETERS</th><th>FLOPS</th><th>ACTIVATION MEMORY (BYTES)</th><th /></tr></thead><tbody>
            {compared.map((item) => { const fewest = Math.min(...compared.map((c) => c.analytical_metrics.parameters))
              return <tr key={item.architecture_id}><td><i className="legend-dot" style={{ background: color(item.architecture_id) }} /><code>{item.architecture_id.slice(0, 12)}</code></td><td>{item.architecture.search_space ?? "—"}</td><td className="mono">{item.architecture.nodes.length}</td><td className="mono">{item.architecture.edges.length}</td>
                <td className="mono">{formatCount(item.analytical_metrics.parameters)}{item.analytical_metrics.parameters === fewest ? " (fewest)" : ""}</td><td className="mono">{formatCount(item.analytical_metrics.flops)}</td><td className="mono">{formatCount(item.analytical_metrics.activation_memory_bytes)}</td>
                <td><button className="button compact" onClick={() => go("explorer", { id: item.architecture_id })}>Open</button></td></tr> })}
          </tbody></table></div>
          <p className="panel-note">★ marks the lowest value per metric. Accuracy is not measured for registered graphs; measure latency per architecture in the Explorer.</p>
        </>}
      </Panel>
      <Panel title="Research result sets" meta="research/results (READ-ONLY)">
        <Loaded poll={sets} label="result sets" isEmpty={(data) => data.items.length === 0} empty="No result sets found on the API host.">{(data) => <div className="result-sets">{data.items.map((item) => <button key={item.name} aria-pressed={item.name === setName} className={item.name === setName ? "active" : ""} onClick={() => setSetName(item.name)}>
          <Icon name="database" /><span><b className="mono">{item.name}</b><small>{item.files.join(", ")}</small></span></button>)}</div>}</Loaded>
      </Panel>
      <Panel title={setName || "Result set"} meta="PROVENANCE" className="span-2">
        <Loaded poll={detail} label="result set">{(data) => <div className="result-detail">
          {data.experiment ? <p className="panel-note">Config: budget {data.experiment.budget} · seeds {data.experiment.seeds.join(", ")} · policies {data.experiment.algorithms.join(", ")}{data.experiment.ablations?.length ? ` · ablations ${data.experiment.ablations.map((item) => item.name).join(", ")}` : ""}</p> : null}
          {data.tables ? <><h3 className="detail-label">TABLES</h3><pre className="raw-json">{data.tables}</pre></> : null}
          {data.predictor ? <><h3 className="detail-label">Predictor report (smoke-scale)</h3><pre className="raw-json">{JSON.stringify(data.predictor, null, 1)}</pre></> : null}
          {data.generator ? <><h3 className="detail-label">Generator report (smoke-scale)</h3><pre className="raw-json">{JSON.stringify(data.generator, null, 1)}</pre></> : null}
          {data.checkpoint_verification ? <><h3 className="detail-label">CHECKPOINT VERIFICATION</h3><pre className="raw-json">{JSON.stringify(data.checkpoint_verification, null, 1)}</pre></> : null}
          {data.readme ? <details><summary>README (provenance)</summary><pre className="raw-json">{data.readme}</pre></details> : null}
          {!data.tables && !data.readme && !data.report && !data.predictor ? <div className="empty-inline">This set has no readable report files.</div> : null}
        </div>}</Loaded>
      </Panel>
      <Panel title="Experiment leaderboard" meta="RANKED BY VALIDATION ONLY" className="span-3">
        <Loaded poll={experiments} label="experiments" isEmpty={() => leaderboard.length === 0} empty="No completed benchmark_lookup or measured_training experiments recorded through the API.">{() => <div className="table-wrap"><table aria-label="Experiment leaderboard"><thead><tr><th>#</th><th>ARCHITECTURE</th><th>EVIDENCE</th><th>VALIDATION %</th><th>TEST %</th></tr></thead><tbody>
          {leaderboard.map((row) => <tr key={row.experimentId}><td className="mono">{row.rank}</td><td><code>{row.architectureId.slice(0, 12)}</code></td><td>{row.evidenceType}</td><td className="mono">{row.validation.toFixed(2)}</td><td className="mono">{row.test === null ? "—" : row.test.toFixed(2)}</td></tr>)}</tbody></table></div>}</Loaded>
      </Panel>
    </div>
  </div>
}
