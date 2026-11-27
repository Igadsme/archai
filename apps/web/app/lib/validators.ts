import type { Validator } from "./api"

const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value)
const isFiniteNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value)

export const healthResponse: Validator = (value) =>
  isObject(value) && typeof value.status === "string" ? null : "expected { status: string }"

export const itemsResponse: Validator = (value) =>
  isObject(value) && Array.isArray(value.items) ? null : "expected { items: [...] }"

export function architectureProblem(value: unknown): string | null {
  if (!isObject(value)) return "architecture must be an object"
  if (!Array.isArray(value.nodes) || value.nodes.length === 0) return "architecture.nodes must be a non-empty array"
  for (const node of value.nodes) {
    if (!isObject(node) || typeof node.id !== "string" || typeof node.op !== "string" || !isFiniteNumber(node.channels)) return "every node needs id, op and channels"
  }
  if (!Array.isArray(value.edges)) return "architecture.edges must be an array"
  for (const edge of value.edges) {
    if (!isObject(edge) || typeof edge.source !== "string" || typeof edge.target !== "string") return "every edge needs source and target"
  }
  const spec = value.input_spec
  if (!isObject(spec) || !isFiniteNumber(spec.channels) || !isFiniteNumber(spec.height) || !isFiniteNumber(spec.width)) return "architecture.input_spec needs channels, height and width"
  return null
}

export function metricsProblem(value: unknown): string | null {
  if (!isObject(value)) return "analytical_metrics must be an object"
  for (const key of ["parameters", "flops", "activation_memory_bytes"]) if (!isFiniteNumber(value[key])) return `analytical_metrics.${key} must be a number`
  return null
}

/** POST /v1/architectures/validate, POST /v1/architectures and GET /v1/architectures/{id}. */
export const architectureDetailResponse: Validator = (value) => {
  if (!isObject(value)) return "expected an object"
  if (typeof value.hash !== "string" || !value.hash) return "missing canonical hash"
  return architectureProblem(value.architecture) ?? metricsProblem(value.analytical_metrics)
}

export const compareResponse: Validator = (value) => {
  if (!isObject(value) || !Array.isArray(value.items)) return "expected { items: [...] }"
  for (const item of value.items) {
    if (!isObject(item) || typeof item.architecture_id !== "string") return "every item needs architecture_id"
    const problem = architectureProblem(item.architecture) ?? metricsProblem(item.analytical_metrics)
    if (problem) return problem
  }
  return null
}

export const generateResponse: Validator = (value) => {
  if (!isObject(value) || !Array.isArray(value.items) || typeof value.checkpoint !== "string") return "expected { items, checkpoint }"
  for (const item of value.items) {
    if (!isObject(item) || typeof item.architecture_id !== "string") return "every candidate needs architecture_id"
    const problem = architectureProblem(item.architecture)
    if (problem) return problem
  }
  return null
}
