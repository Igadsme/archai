"use client"
import { Empty, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import { buildLeaderboard } from "../lib/leaderboard"
import type { ExperimentItem } from "../lib/types"

export default function Leaderboard() {
  const rows = buildLeaderboard(items(usePoll<{ items: ExperimentItem[] }>("/v1/experiments").data))
  return <>
    <PageHeader eyebrow="LEADERBOARD" title="Ranked by validation accuracy" note="Test accuracy is shown for reference and never used for ranking. Predicted evidence is excluded." />
    <article className="panel">{rows.length === 0 ? <Empty>No benchmark or measured experiments with validation_accuracy yet.</Empty> : <table><thead><tr><th>#</th><th>Architecture</th><th>Evidence</th><th>Validation</th><th>Test (held out)</th></tr></thead><tbody>{rows.map((row) => <tr key={row.experimentId}><td>{row.rank}</td><td><code>{row.architectureId.slice(0, 12)}</code></td><td>{row.evidenceType}</td><td>{row.validation.toFixed(2)}</td><td>{row.test === null ? "—" : row.test.toFixed(2)}</td></tr>)}</tbody></table>}</article>
  </>
}
