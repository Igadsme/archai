import { layoutDag } from "./graph"
import type { FullArchitecture } from "./types"

export const NODE_WIDTH = 100
export const NODE_HEIGHT = 80
const LAYER_SPACING = 145
const ROW_SPACING = 110
const MARGIN = 40
const LANE_GAP = 16

export type EdgeKind = "data" | "residual" | "branch"

/** Tensor shape without the batch dimension: [channels, height, width]. */
export type TensorShape = [number, number, number]

export type GraphNodeModel = {
  index: number
  id: string
  op: string
  group: string
  declaredChannels: number
  kernelSize: number | null
  normalization: string | null
  activation: string | null
  layer: number
  x: number
  y: number
  inputShape: TensorShape | null
  outputShape: TensorShape
  /** Analytical cost of this node alone, using the formulas of archai_compiler.metrics.analytical_metrics. */
  parameters: number
  flops: number
  activationBytes: number
  incoming: string[]
  outgoing: string[]
  fanIn: number
  /** PyTorch modules archai_compiler.pytorch_compiler builds for this node. */
  module: string
}

export type GraphEdgeModel = {
  id: string
  source: string
  target: string
  from: number
  to: number
  kind: EdgeKind
  shape: TensorShape
  span: number
  path: string
}

export type GraphModel = {
  nodes: GraphNodeModel[]
  edges: GraphEdgeModel[]
  width: number
  height: number
  layers: number
  groups: string[]
  totals: { parameters: number; flops: number; activationMemoryBytes: number }
  residualCount: number
  branchCount: number
}

export const opGroup = (op: string): string => ({
  input: "INPUT", output: "OUTPUT", conv3x3: "CONV 3×3", conv1x1: "CONV 1×1", avg_pool3x3: "POOL", skip: "SKIP", none: "ZERO",
} as Record<string, string>)[op] ?? op.toUpperCase()

export const formatShape = (shape: TensorShape | null): string => shape ? `[B, ${shape[0]}, ${shape[1]}, ${shape[2]}]` : "—"

function compilerModule(op: string, inChannels: number, node: FullArchitecture["nodes"][number]): string {
  if (op === "input") return "x = input  # graph input"
  if (op === "output") return "out = x  # → flatten(1) → nn.LazyLinear(output_classes)"
  if (op === "skip") return "x = x  # identity"
  if (op === "none") return "x = torch.zeros_like(x)"
  if (op === "avg_pool3x3") return "nn.AvgPool2d(3, stride=1, padding=1)"
  const kernel = op === "conv3x3" ? node.kernel_size ?? 3 : 1
  const layers = [`nn.Conv2d(${inChannels}, ${node.channels}, ${kernel}, padding=${Math.floor(kernel / 2)}, bias=True)`]
  if ((node.normalization ?? "batch") === "batch") layers.push(`nn.BatchNorm2d(${node.channels})`)
  else if (node.normalization === "layer") layers.push(`nn.GroupNorm(1, ${node.channels})`)
  if ((node.activation ?? "relu") === "relu") layers.push("nn.ReLU()")
  else if (node.activation === "gelu") layers.push("nn.GELU()")
  return `nn.Sequential(\n  ${layers.join(",\n  ")},\n)`
}

/**
 * Map a validated architecture (archai_core.schema.Architecture as returned by the API) to a renderable graph.
 * Shapes and per-node costs follow archai_compiler: the first incoming edge sets in_channels, convolutions keep
 * the spatial size (padding = kernel // 2) and multi-input nodes reduce their inputs element-wise.
 */
export function buildGraphModel(architecture: FullArchitecture): GraphModel {
  const ids = architecture.nodes.map((node) => node.id)
  const byId = new Map(architecture.nodes.map((node) => [node.id, node]))
  const incoming = new Map(ids.map((id) => [id, [] as string[]]))
  const outgoing = new Map(ids.map((id) => [id, [] as string[]]))
  for (const edge of architecture.edges) {
    incoming.get(edge.target)?.push(edge.source)
    outgoing.get(edge.source)?.push(edge.target)
  }
  const layout = layoutDag(ids, architecture.edges, { x: LAYER_SPACING, y: ROW_SPACING, margin: MARGIN })
  const layerOf = new Map(layout.nodes.map((node) => [node.id, node.layer]))
  const layers = Math.max(0, ...layout.nodes.map((node) => node.layer)) + 1
  const rowsPerLayer = new Map<number, number>()
  for (const node of layout.nodes) rowsPerLayer.set(node.layer, (rowsPerLayer.get(node.layer) ?? 0) + 1)
  const maxRows = Math.max(1, ...Array.from(rowsPerLayer.values()))

  const { height: h, width: w, channels: inputChannels } = architecture.input_spec
  const order = [...layout.nodes].sort((a, b) => a.layer - b.layer || a.row - b.row).map((node) => node.id)
  const channels = new Map<string, number>()
  const cost = new Map<string, { parameters: number; flops: number; inChannels: number }>()
  for (const id of order) {
    const node = byId.get(id)!
    if (node.op === "input") { channels.set(id, inputChannels); cost.set(id, { parameters: 0, flops: 0, inChannels: inputChannels }); continue }
    const first = incoming.get(id)?.[0]
    const inChannels = first !== undefined ? channels.get(first) ?? inputChannels : inputChannels
    let parameters = 0
    let flops = 0
    if (node.op === "conv3x3" || node.op === "conv1x1") {
      const kernel = node.op === "conv3x3" ? node.kernel_size ?? 3 : 1
      parameters = inChannels * node.channels * kernel * kernel + node.channels
      flops = 2 * h * w * inChannels * node.channels * kernel * kernel
      channels.set(id, node.channels)
    } else {
      if (node.op === "avg_pool3x3") flops = h * w * inChannels * 9
      channels.set(id, inChannels)
    }
    cost.set(id, { parameters, flops, inChannels })
  }

  const position = new Map(layout.nodes.map((node) => {
    const offset = ((maxRows - (rowsPerLayer.get(node.layer) ?? 1)) * ROW_SPACING) / 2
    return [node.id, { x: MARGIN + node.layer * LAYER_SPACING, y: MARGIN + 18 + offset + node.row * ROW_SPACING }]
  }))
  const nodes: GraphNodeModel[] = architecture.nodes.map((node, index) => {
    const nodeCost = cost.get(node.id) ?? { parameters: 0, flops: 0, inChannels: inputChannels }
    const out = channels.get(node.id) ?? node.channels
    const isConv = node.op === "conv3x3" || node.op === "conv1x1"
    return {
      index, id: node.id, op: node.op, group: opGroup(node.op), declaredChannels: node.channels,
      kernelSize: node.op === "conv3x3" ? node.kernel_size ?? 3 : node.op === "conv1x1" ? 1 : node.op === "avg_pool3x3" ? 3 : null,
      normalization: isConv ? node.normalization ?? "batch" : null, activation: isConv ? node.activation ?? "relu" : null,
      layer: layerOf.get(node.id) ?? 0, ...position.get(node.id)!,
      inputShape: node.op === "input" ? null : [nodeCost.inChannels, h, w], outputShape: [out, h, w],
      parameters: nodeCost.parameters, flops: nodeCost.flops, activationBytes: h * w * out * 4,
      incoming: incoming.get(node.id) ?? [], outgoing: outgoing.get(node.id) ?? [], fanIn: incoming.get(node.id)?.length ?? 0,
      module: compilerModule(node.op, nodeCost.inChannels, node),
    }
  })
  const indexOf = new Map(nodes.map((node) => [node.id, node.index]))
  const bottom = MARGIN + 18 + maxRows * ROW_SPACING - (ROW_SPACING - NODE_HEIGHT)
  let lane = 0
  const edges: GraphEdgeModel[] = architecture.edges.map((edge) => {
    const source = nodes[indexOf.get(edge.source)!]
    const target = nodes[indexOf.get(edge.target)!]
    const span = target.layer - source.layer
    const kind: EdgeKind = span > 1 ? "residual" : (outgoing.get(edge.source)?.length ?? 0) > 1 ? "branch" : "data"
    let path: string
    if (kind === "residual") {
      const y = bottom + 14 + lane * LANE_GAP
      lane += 1
      path = `M${source.x + NODE_WIDTH / 2} ${source.y + NODE_HEIGHT}V${y}H${target.x + NODE_WIDTH / 2 + 8}V${target.y + NODE_HEIGHT}`
    } else {
      const sx = source.x + NODE_WIDTH
      const sy = source.y + NODE_HEIGHT / 2
      const tx = target.x
      const ty = target.y + NODE_HEIGHT / 2
      const mid = Math.round((sx + tx) / 2)
      path = sy === ty ? `M${sx} ${sy}H${tx}` : `M${sx} ${sy}H${mid}V${ty}H${tx}`
    }
    return { id: `${edge.source}->${edge.target}`, source: edge.source, target: edge.target, from: source.index, to: target.index, kind, shape: source.outputShape, span, path }
  })
  const width = MARGIN * 2 + (layers - 1) * LAYER_SPACING + NODE_WIDTH
  const height = bottom + 24 + lane * LANE_GAP + MARGIN / 2
  const groups = Array.from(new Set(nodes.map((node) => node.group)))
  return {
    nodes, edges, width, height, layers, groups,
    totals: {
      parameters: nodes.reduce((sum, node) => sum + node.parameters, 0),
      flops: nodes.reduce((sum, node) => sum + node.flops, 0),
      activationMemoryBytes: h * w * Math.max(...nodes.map((node) => node.outputShape[0])) * 4,
    },
    residualCount: edges.filter((edge) => edge.kind === "residual").length,
    branchCount: edges.filter((edge) => edge.kind === "branch").length,
  }
}

/** Node ids and ops that differ between two architectures (used by compare mode). */
export function diffArchitectures(base: FullArchitecture, other: FullArchitecture): { added: string[]; removed: string[]; changed: string[]; edgeDelta: number } {
  const baseNodes = new Map(base.nodes.map((node) => [node.id, node]))
  const otherNodes = new Map(other.nodes.map((node) => [node.id, node]))
  const added = other.nodes.filter((node) => !baseNodes.has(node.id)).map((node) => node.id)
  const removed = base.nodes.filter((node) => !otherNodes.has(node.id)).map((node) => node.id)
  const changed = other.nodes.filter((node) => {
    const previous = baseNodes.get(node.id)
    return previous && (previous.op !== node.op || previous.channels !== node.channels || (previous.kernel_size ?? 3) !== (node.kernel_size ?? 3))
  }).map((node) => node.id)
  const key = (edge: { source: string; target: string }) => `${edge.source}->${edge.target}`
  const baseEdges = new Set(base.edges.map(key))
  const otherEdges = new Set(other.edges.map(key))
  const edgeDelta = Array.from(otherEdges).filter((edge) => !baseEdges.has(edge)).length + Array.from(baseEdges).filter((edge) => !otherEdges.has(edge)).length
  return { added, removed, changed, edgeDelta }
}
