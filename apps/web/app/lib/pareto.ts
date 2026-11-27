import type { HistoryStep, ParetoPoint } from "./types"

/** Non-dominated points (maximize validation accuracy, minimize params), sorted by params. */
export function paretoFront(points: ParetoPoint[]): ParetoPoint[] {
  const ordered = [...points].sort((a, b) => a.params_m - b.params_m || b.validation_accuracy - a.validation_accuracy)
  const front: ParetoPoint[] = []
  let best = Number.NEGATIVE_INFINITY
  for (const point of ordered) {
    if (point.validation_accuracy > best) { front.push(point); best = point.validation_accuracy }
  }
  return front
}

/** 2D hypervolume w.r.t. (reference accuracy, reference params); matches archai_benchmark.hypervolume_2d. */
export function hypervolume(points: ParetoPoint[], reference: [number, number]): number {
  const [refAccuracy, refCost] = reference
  const front = paretoFront(points.filter((p) => p.validation_accuracy >= refAccuracy && p.params_m <= refCost))
  let area = 0
  for (let i = 0; i < front.length; i += 1) {
    const nextCost = i + 1 < front.length ? front[i + 1].params_m : refCost
    area += (front[i].validation_accuracy - refAccuracy) * (nextCost - front[i].params_m)
  }
  return area
}

/** Points from a worker search history that carry a parameter cost. */
export function historyPoints(history: HistoryStep[]): ParetoPoint[] {
  return history.filter((step) => typeof step.params_m === "number")
    .map((step) => ({ index: step.index, architecture_string: step.architecture_string, validation_accuracy: step.validation_accuracy, params_m: step.params_m as number }))
}
