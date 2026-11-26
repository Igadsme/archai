// Pure request builders for Studio forms. They mirror the API's server-side
// validation so users get errors before submitting; the API stays authoritative.

export type Result<T> = { ok: true; value: T } | { ok: false; errors: string[] }

export const SEARCH_ALGORITHMS = ["random", "evolution", "bayesian"] as const
export type SearchForm = { algorithm: string; datasetId: string; budget: string; seed: string; indices: string }
export type SearchRequest = { algorithm: string; dataset_id: string; budget_evaluations: number; seed: number; indices: number[] }

export const defaultSearchForm: SearchForm = { algorithm: "bayesian", datasetId: "cifar10", budget: "10", seed: "0", indices: "0:256" }

const integer = (raw: string): number | null => (/^-?\d+$/.test(raw.trim()) ? Number(raw.trim()) : null)

/** Parse "0:256" (half-open range) and/or comma-separated indices, e.g. "1,2,10:20"; returns sorted unique indices. */
export function parseIndices(raw: string, maxCount = 100_000): Result<number[]> {
  const values: number[] = []
  for (const part of raw.split(",").map((item) => item.trim()).filter(Boolean)) {
    const range = /^(\d+):(\d+)$/.exec(part)
    if (range) {
      const start = Number(range[1]); const stop = Number(range[2])
      if (stop <= start) return { ok: false, errors: [`range ${part} must satisfy start < stop`] }
      if (values.length + (stop - start) > maxCount) return { ok: false, errors: [`at most ${maxCount} indices`] }
      for (let index = start; index < stop; index += 1) values.push(index)
    } else if (/^\d+$/.test(part)) {
      values.push(Number(part))
    } else {
      return { ok: false, errors: [`invalid index entry: ${part}`] }
    }
  }
  if (values.length > maxCount) return { ok: false, errors: [`at most ${maxCount} indices`] }
  return { ok: true, value: Array.from(new Set(values)).sort((left, right) => left - right) }
}

export function buildSearchRequest(form: SearchForm): Result<SearchRequest> {
  const errors: string[] = []
  if (!(SEARCH_ALGORITHMS as readonly string[]).includes(form.algorithm)) errors.push("algorithm must be random, evolution or bayesian")
  const datasetId = form.datasetId.trim()
  if (!datasetId || datasetId.length > 128) errors.push("dataset is required (max 128 characters)")
  const budget = integer(form.budget)
  if (budget === null || budget <= 0 || budget > 1_000_000) errors.push("budget must be an integer in [1, 1000000]")
  const seed = integer(form.seed)
  if (seed === null) errors.push("seed must be an integer")
  const indices = form.indices.trim() ? parseIndices(form.indices) : ({ ok: true, value: [] } as Result<number[]>)
  if (!indices.ok) errors.push(...indices.errors)
  else if (budget !== null && indices.value.length > 0 && budget > indices.value.length) errors.push(`budget (${budget}) exceeds the ${indices.value.length}-architecture pool`)
  if (errors.length || budget === null || seed === null || !indices.ok) return { ok: false, errors }
  return { ok: true, value: { algorithm: form.algorithm, dataset_id: datasetId, budget_evaluations: budget, seed, indices: indices.value } }
}

export type TrainingKind = "candidate" | "generator" | "predictor"
export type TrainingForm = {
  kind: TrainingKind; epochs: string; seed: string; checkpointPath: string
  architectureJson: string; corpusPath: string; benchmarkPath: string; benchmarkSha256: string; indices: string
}
export type TrainingRequest = { kind: TrainingKind; payload: Record<string, unknown> }

export const defaultCandidateArchitecture = {
  nodes: [{ id: "input", op: "input", channels: 3 }, { id: "conv", op: "conv3x3", channels: 8 }, { id: "output", op: "output", channels: 8 }],
  edges: [{ source: "input", target: "conv" }, { source: "conv", target: "output" }],
  input_spec: { channels: 3, height: 8, width: 8 }, output_classes: 10,
}

export const defaultTrainingForm: TrainingForm = {
  kind: "candidate", epochs: "1", seed: "0", checkpointPath: "/tmp/archai-candidate.pt",
  architectureJson: JSON.stringify(defaultCandidateArchitecture), corpusPath: "", benchmarkPath: "", benchmarkSha256: "", indices: "0:64",
}

export function buildTrainingRequest(form: TrainingForm): Result<TrainingRequest> {
  const errors: string[] = []
  const epochs = integer(form.epochs)
  if (epochs === null || epochs <= 0 || epochs > 1000) errors.push("epochs must be an integer in [1, 1000]")
  const seed = integer(form.seed)
  if (seed === null) errors.push("seed must be an integer")
  const payload: Record<string, unknown> = { epochs, seed }
  const absolute = (value: string, field: string) => {
    if (!value.trim().startsWith("/")) errors.push(`${field} must be an absolute path`)
    return value.trim()
  }
  if (form.kind === "candidate") {
    try {
      const architecture = JSON.parse(form.architectureJson) as unknown
      if (typeof architecture !== "object" || architecture === null || Array.isArray(architecture)) errors.push("architecture must be a JSON object")
      payload.architecture = architecture
    } catch { errors.push("architecture must be valid JSON") }
    payload.dataset = "synthetic"
    if (form.checkpointPath.trim()) payload.checkpoint_path = absolute(form.checkpointPath, "checkpoint path")
  } else if (form.kind === "generator") {
    payload.corpus_path = absolute(form.corpusPath, "corpus path")
    payload.checkpoint_path = absolute(form.checkpointPath, "checkpoint path")
  } else if (form.kind === "predictor") {
    payload.benchmark_path = absolute(form.benchmarkPath, "benchmark path")
    payload.checkpoint_path = absolute(form.checkpointPath, "checkpoint path")
    if (!/^[0-9a-fA-F]{64}$/.test(form.benchmarkSha256.trim())) errors.push("benchmark SHA-256 must be 64 hex characters")
    payload.benchmark_sha256 = form.benchmarkSha256.trim().toLowerCase()
    const indices = parseIndices(form.indices)
    if (!indices.ok) errors.push(...indices.errors)
    else if (indices.value.length < 3) errors.push("predictor training needs at least three indices")
    else payload.indices = indices.value
  } else {
    errors.push("unknown training kind")
  }
  return errors.length ? { ok: false, errors } : { ok: true, value: { kind: form.kind, payload } }
}
