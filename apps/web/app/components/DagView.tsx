"use client"
import { layoutDag } from "../lib/graph"
import type { FullArchitecture } from "../lib/types"

/** SVG rendering of a validated architecture DAG (layered layout, one box per node). */
export function DagView({ architecture }: { architecture: FullArchitecture }) {
  const layout = layoutDag(architecture.nodes.map((node) => node.id), architecture.edges)
  const position = new Map(layout.nodes.map((node) => [node.id, node]))
  const ops = new Map(architecture.nodes.map((node) => [node.id, node]))
  return <div className="dag-scroll"><svg role="img" aria-label={`Architecture graph with ${architecture.nodes.length} nodes and ${architecture.edges.length} edges`}
    width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`}>
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6f86a8" /></marker></defs>
    {architecture.edges.map((edge) => {
      const a = position.get(edge.source); const b = position.get(edge.target)
      return a && b ? <line key={`${edge.source}-${edge.target}`} x1={a.x + 100} y1={a.y + 15} x2={b.x} y2={b.y + 15} stroke="#6f86a8" markerEnd="url(#arrow)" /> : null
    })}
    {layout.nodes.map((node) => {
      const spec = ops.get(node.id)
      return <g key={node.id}><rect x={node.x} y={node.y} width={100} height={30} rx={6} fill="#19263d" stroke="#477782" />
        <text x={node.x + 50} y={node.y + 13} textAnchor="middle" fontSize="10" fill="#e8eefc">{node.id.slice(0, 14)}</text>
        <text x={node.x + 50} y={node.y + 25} textAnchor="middle" fontSize="9" fill="#8fa3c2">{spec?.op} · {spec?.channels}ch</text></g>
    })}
  </svg></div>
}
