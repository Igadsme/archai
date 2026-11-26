import type { ArchitectureEdge } from "./types"

export type LayoutNode = { id: string; layer: number; row: number; x: number; y: number }

/** Layered layout of a DAG: layer = longest path from a source; rows ordered by first appearance. */
export function layoutDag(nodeIds: string[], edges: ArchitectureEdge[], spacing = { x: 150, y: 70, margin: 40 }): { nodes: LayoutNode[]; width: number; height: number } {
  const incoming = new Map(nodeIds.map((id) => [id, [] as string[]]))
  for (const edge of edges) incoming.get(edge.target)?.push(edge.source)
  const layer = new Map<string, number>()
  const visiting = new Set<string>()
  const depth = (id: string): number => {
    const known = layer.get(id)
    if (known !== undefined) return known
    if (visiting.has(id)) throw new Error(`cycle at ${id}`)
    visiting.add(id)
    const value = Math.max(-1, ...(incoming.get(id) ?? []).map(depth)) + 1
    visiting.delete(id)
    layer.set(id, value)
    return value
  }
  nodeIds.forEach(depth)
  const rows = new Map<number, number>()
  const nodes = nodeIds.map((id) => {
    const l = layer.get(id) ?? 0
    const row = rows.get(l) ?? 0
    rows.set(l, row + 1)
    return { id, layer: l, row, x: spacing.margin + l * spacing.x, y: spacing.margin + row * spacing.y }
  })
  const layers = Math.max(0, ...nodes.map((node) => node.layer)) + 1
  const maxRows = Math.max(1, ...Array.from(rows.values()))
  return { nodes, width: spacing.margin * 2 + (layers - 1) * spacing.x + 100, height: spacing.margin * 2 + (maxRows - 1) * spacing.y + 30 }
}
