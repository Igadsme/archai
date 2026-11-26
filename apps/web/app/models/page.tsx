"use client"
import { Empty, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import type { ModelItem } from "../lib/types"

export default function Models() {
  const models = items(usePoll<{ items: ModelItem[] }>("/v1/models").data)
  return <>
    <PageHeader eyebrow="MODEL REGISTRY" title="Checksum-backed checkpoints" note="Integrity is re-verified against the registered SHA-256 on every read." />
    <article className="panel">{models.length === 0 ? <Empty>No model checkpoints registered.</Empty> : <table><thead><tr><th>Model</th><th>Kind</th><th>Version</th><th>SHA-256</th><th>Integrity</th></tr></thead><tbody>{models.map((item) => <tr key={`${item.model_id}-${item.version}`}><td>{item.model_id}</td><td>{item.kind}</td><td>{item.version}</td><td><code>{item.sha256.slice(0, 12)}</code></td><td>{item.integrity_verified === undefined ? "—" : item.integrity_verified ? "verified" : "MISMATCH or missing"}</td></tr>)}</tbody></table>}</article>
  </>
}
