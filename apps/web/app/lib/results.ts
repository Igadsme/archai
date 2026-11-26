import type { ResearchResult, SeedSummary } from "./types"

/** Split a result set's algorithms into primary policies and ablations, using the committed experiment config. */
export function splitAblations(result: ResearchResult): { policies: string[]; ablations: string[] } {
  const names = Object.keys(result.report?.algorithms ?? {})
  const ablation = new Set((result.experiment?.ablations ?? []).map((item) => item.name))
  const byBest = (a: string, b: string) => (result.report!.algorithms[b].best_validation_accuracy.mean - result.report!.algorithms[a].best_validation_accuracy.mean)
  return { policies: names.filter((name) => !ablation.has(name)).sort(byBest), ablations: names.filter((name) => ablation.has(name)).sort(byBest) }
}

/** "mean [low, high]" with fixed digits, or an em dash when the metric was not measured. */
export function ci(summary: SeedSummary | undefined, digits = 2): string {
  return summary ? `${summary.mean.toFixed(digits)} [${summary.ci_low.toFixed(digits)}, ${summary.ci_high.toFixed(digits)}]` : "—"
}

/** True when two 95% intervals do not overlap (a conservative, not a formal, significance signal). */
export function separated(a: SeedSummary | undefined, b: SeedSummary | undefined): boolean {
  return !!a && !!b && (a.ci_low > b.ci_high || b.ci_low > a.ci_high)
}

/** The worker stores a handler's return value at job.payload.result (archai_shared.worker.WorkerRunner). */
export function jobResult<T = Record<string, unknown>>(job: { payload?: Record<string, unknown>; result?: unknown } | null | undefined): T | null {
  const value = job?.payload?.result ?? job?.result
  return value && typeof value === "object" ? value as T : null
}
