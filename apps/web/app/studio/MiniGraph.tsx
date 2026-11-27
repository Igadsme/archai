"use client"
import { useMemo } from "react"
import { buildGraphModel, NODE_HEIGHT, NODE_WIDTH } from "../lib/architectureGraph"
import type { FullArchitecture } from "../lib/types"

/** Read-only thumbnail of a validated architecture graph. */
export function MiniGraph({ architecture, label }: { architecture: FullArchitecture; label: string }) {
  const model = useMemo(() => { try { return buildGraphModel(architecture) } catch { return null } }, [architecture])
  if (!model) return <div className="mini-graph invalid">Graph could not be laid out (cycle or dangling edge).</div>
  return <svg className="mini-graph" viewBox={`0 0 ${model.width} ${model.height}`} role="img" aria-label={`${label}: ${model.nodes.length} nodes, ${model.edges.length} edges`}>
    {model.edges.map((edge) => <path key={edge.id} d={edge.path} className={`mini-edge ${edge.kind}`} />)}
    {model.nodes.map((node) => <g key={node.id} transform={`translate(${node.x} ${node.y})`} className={`mini-node operator-${node.op}`}>
      <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx="2" /><rect className="node-accent" width="3" height={NODE_HEIGHT} />
      <text x="10" y="22" className="mini-op">{node.op.toUpperCase()}</text><text x="10" y="46" className="mini-id">{node.id.slice(0, 14)}</text>
      <text x="10" y="66" className="mini-shape">{node.outputShape[0]}×{node.outputShape[1]}×{node.outputShape[2]}</text>
    </g>)}
  </svg>
}
