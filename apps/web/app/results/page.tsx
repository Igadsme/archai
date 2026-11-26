"use client"
import { useState } from "react"
import { Empty, Loaded, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { buildLeaderboard } from "../lib/leaderboard"
import type { ExperimentItem, ResearchResult } from "../lib/types"

type ResultSet = { name: string; files: string[] }

export default function ResearchResults() {
  const sets = usePoll<{ items: ResultSet[]; root_available: boolean }>("/v1/research/results", 0)
  const [name, setName] = useState("nasbench201_cifar10_full_suite")
  const detail = usePoll<ResearchResult>(name ? `/v1/research/results/${name}` : null, 0)
  const experiments = usePoll<{ items: ExperimentItem[] }>("/v1/experiments", 15000)
  const leaderboard = buildLeaderboard(items(experiments.data))
  return <>
    <PageHeader eyebrow="RESEARCH RESULTS" title="Committed, measured result sets" note="Served read-only from research/results in the repository. Each set states its evidence type (benchmark_lookup or smoke-scale training); nothing here is predicted or extrapolated." />
    <div className="grid">
      <article className="panel"><h3>Result sets</h3>
        <Loaded poll={sets} isEmpty={(data) => items(data).length === 0} empty="No result sets found on the API host.">{(data) => <ul>{items(data).map((item) => <li key={item.name}>
          <button className="link-button" aria-pressed={item.name === name} onClick={() => setName(item.name)}><code>{item.name}</code></button><span>{item.files.join(", ")}</span></li>)}</ul>}</Loaded>
      </article>
      <article className="panel"><h3>Experiment leaderboard</h3>
        <Loaded poll={experiments} isEmpty={() => leaderboard.length === 0} empty="No completed benchmark_lookup or measured_training experiments recorded through the API.">{() => <div className="table-scroll"><table><thead><tr><th>#</th><th>Architecture</th><th>Evidence</th><th>Validation</th><th>Test</th></tr></thead><tbody>
          {leaderboard.map((row) => <tr key={row.experimentId}><td>{row.rank}</td><td><code>{row.architectureId.slice(0, 12)}</code></td><td>{row.evidenceType}</td><td className="num">{row.validation.toFixed(2)}</td><td className="num">{row.test === null ? "—" : row.test.toFixed(2)}</td></tr>)}</tbody></table></div>}</Loaded>
      </article>
      <article className="panel wide"><h3>{name || "Select a result set"}</h3>
        {!name ? <Empty>Select a result set.</Empty> : <Loaded poll={detail}>{(data) => <>
          {data.experiment ? <p className="muted">Config: budget {data.experiment.budget} · seeds {data.experiment.seeds.join(", ")} · policies {data.experiment.algorithms.join(", ")}{data.experiment.ablations?.length ? ` · ablations ${data.experiment.ablations.map((item) => item.name).join(", ")}` : ""}</p> : null}
          {data.tables ? <><h3>Tables</h3><pre className="readme">{data.tables}</pre></> : null}
          {data.readme ? <><h3>README (provenance)</h3><pre className="readme">{data.readme}</pre></> : null}
          {data.predictor ? <><h3>Predictor report (smoke-scale)</h3><pre className="readme">{JSON.stringify(data.predictor, null, 1)}</pre></> : null}
          {data.generator ? <><h3>Generator report (smoke-scale)</h3><pre className="readme">{JSON.stringify(data.generator, null, 1)}</pre></> : null}
          {data.checkpoint_verification ? <><h3>Checkpoint verification</h3><pre className="readme">{JSON.stringify(data.checkpoint_verification, null, 1)}</pre></> : null}
          {!data.tables && !data.readme && !data.report ? <Empty>This set has no readable report files.</Empty> : null}
        </>}</Loaded>}
      </article>
    </div>
  </>
}
