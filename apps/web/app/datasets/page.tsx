"use client"
import { Empty, PageHeader } from "../components/Shell"
import { items, usePoll } from "../components/usePoll"
import type { DatasetItem } from "../lib/types"

export default function Datasets() {
  const datasets = items(usePoll<{ items: DatasetItem[] }>("/v1/datasets").data)
  return <>
    <PageHeader eyebrow="DATASETS" title="Immutable, checksum-registered versions" note="Benchmark and measured evidence must reference a registered dataset version with a matching checksum." />
    <article className="panel">{datasets.length === 0 ? <Empty>No datasets registered.</Empty> : <table><thead><tr><th>Dataset</th><th>Version</th><th>SHA-256</th><th>License</th></tr></thead><tbody>{datasets.map((item) => <tr key={`${item.dataset_id}-${item.version}`}><td>{item.dataset_id}</td><td>{item.version}</td><td><code>{item.checksum.slice(0, 16)}</code></td><td>{item.license ?? "—"}</td></tr>)}</tbody></table>}</article>
  </>
}
