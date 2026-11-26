"use client"
import { useState } from "react"
import { Scatter, type Series } from "../components/Scatter"
import { Empty, Loaded, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { historyPoints, hypervolume, paretoFront } from "../lib/pareto"
import { jobResult } from "../lib/results"
import type { HistoryStep, JobDetail, ResearchResult, SearchItem } from "../lib/types"

const COLORS = ["#7fe0d2", "#e7aa67", "#9db7ff", "#e36b79", "#c49bff", "#b7e07f", "#f0d27f", "#8fa3c2"]
type Session = SearchItem & { job?: JobDetail }

export default function ParetoOptimizationExplorer() {
  const suite = usePoll<ResearchResult>("/v1/research/results/nasbench201_cifar10_full_suite", 0)
  const searches = usePoll<{ items: Session[] }>("/v1/searches", 10000)
  const [seed, setSeed] = useState("0")
  const [shown, setShown] = useState<string[]>(["multi_objective", "random", "bayesian"])
  const [sessionId, setSessionId] = useState("")
  const session = items(searches.data).find((item) => item.search_id === sessionId)
  const sessionHistory = jobResult<{ history?: HistoryStep[] }>(session?.job)?.history ?? []
  const sessionPoints = historyPoints(sessionHistory)
  return <>
    <PageHeader eyebrow="PARETO OPTIMIZATION EXPLORER" title="Accuracy vs. parameters" note="Objectives: maximize NATS-Bench cifar10-valid validation accuracy, minimize parameters (M). Evidence: benchmark_lookup. Hypervolume reference (0 %, 1.6 M)." />
    <div className="grid">
      <article className="panel wide"><h3>Measured search suite (budget 100, 10 seeds)</h3>
        <Loaded poll={suite} isEmpty={(data) => !data.pareto} empty="This result set has no pareto.json.">{(data) => {
          const pareto = data.pareto!
          const policies = Object.keys(pareto.policies)
          const seeds = Object.keys(pareto.policies[policies[0]] ?? {})
          const series: Series[] = [{ label: "full-space front (oracle, seed-0 trial)", color: "#5b6b86", points: pareto.full_space_front_trial_seed_for_seed0, line: true },
            ...shown.filter((name) => pareto.policies[name]?.[seed]).map((name) => ({ label: `${name} (seed ${seed})`, color: COLORS[policies.indexOf(name) % COLORS.length], points: pareto.policies[name][seed].front, line: true }))]
          return <>
            <div className="form-row">
              <label>Seed<select value={seed} onChange={(event) => setSeed(event.target.value)}>{seeds.map((value) => <option key={value}>{value}</option>)}</select></label>
            </div>
            <fieldset className="checks"><legend className="label">Policies shown</legend>{policies.map((name) => <label key={name}><input type="checkbox" checked={shown.includes(name)}
              onChange={(event) => setShown(event.target.checked ? [...shown, name] : shown.filter((value) => value !== name))} />{name}</label>)}</fieldset>
            <Scatter title={`Pareto fronts found by each policy for seed ${seed}`} series={series} />
            <div className="table-scroll"><table><thead><tr><th>Policy</th><th>Front size (seed {seed})</th><th>Hypervolume (seed {seed})</th><th>Hypervolume mean [95% CI], all seeds</th></tr></thead><tbody>
              {policies.map((name) => { const run = pareto.policies[name][seed]; const summary = data.report?.algorithms[name]?.hypervolume_validation_params
                return <tr key={name}><td>{name}</td><td className="num">{run?.front.length ?? "—"}</td><td className="num">{run?.hypervolume?.toFixed(2) ?? "—"}</td>
                  <td className="num">{summary ? `${summary.mean.toFixed(2)} [${summary.ci_low.toFixed(2)}, ${summary.ci_high.toFixed(2)}]` : "—"}</td></tr> })}
            </tbody></table></div>
          </>
        }}</Loaded>
      </article>
      <article className="panel wide"><h3>Live search session</h3>
        <Loaded poll={searches} isEmpty={(data) => items(data).length === 0} empty="No search sessions yet. Launch one in the Autonomous Search Laboratory.">{(data) => <>
          <label>Session<select value={sessionId} onChange={(event) => setSessionId(event.target.value)}><option value="">Choose a session</option>
            {items(data).map((item) => <option key={item.search_id} value={item.search_id}>{item.algorithm} · seed {item.seed} · {item.status} · {item.search_id.slice(0, 8)}</option>)}</select></label>
          {!sessionId ? null : sessionPoints.length === 0 ? <Empty>This session has no evaluated points with a parameter cost yet (status: {session?.status}).</Empty> : <>
            <Scatter title="Evaluated cells and their Pareto front for the selected session" series={[{ label: "evaluated", color: "#3d5a80", points: sessionPoints }, { label: "front", color: "#7fe0d2", points: paretoFront(sessionPoints), line: true }]} />
            <p className="muted">{sessionPoints.length} evaluated · front size {paretoFront(sessionPoints).length} · hypervolume {hypervolume(sessionPoints, [0, 1.6]).toFixed(2)} (computed in the browser from the worker history)</p>
          </>}
        </>}</Loaded>
      </article>
    </div>
  </>
}
