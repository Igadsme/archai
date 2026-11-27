/** Live progress the worker writes to job.payload.progress (archai_shared.worker.report_progress). */
export type TrainingProgress = { phase: "training"; epochs_completed: number; epochs: number; history: Record<string, number>[]; reported_at?: string }
export type SearchProgress = { phase: "searching"; evaluations: number; budget: number; best_validation_accuracy?: number | null; reported_at?: string }
export type JobProgress = TrainingProgress | SearchProgress

const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value)

export function jobProgress(job: { payload?: Record<string, unknown> } | null | undefined): JobProgress | null {
  const value = job?.payload?.progress
  if (!value || typeof value !== "object") return null
  const progress = value as Record<string, unknown>
  if (progress.phase === "training" && isNumber(progress.epochs_completed) && isNumber(progress.epochs)) {
    const history = Array.isArray(progress.history) ? progress.history.filter((row): row is Record<string, number> => !!row && typeof row === "object") : []
    return { phase: "training", epochs_completed: progress.epochs_completed, epochs: progress.epochs, history, reported_at: progress.reported_at as string | undefined }
  }
  if (progress.phase === "searching" && isNumber(progress.evaluations) && isNumber(progress.budget)) {
    return { phase: "searching", evaluations: progress.evaluations, budget: progress.budget,
      best_validation_accuracy: isNumber(progress.best_validation_accuracy) ? progress.best_validation_accuracy : null, reported_at: progress.reported_at as string | undefined }
  }
  return null
}

/** Completed fraction in [0, 1]. */
export function progressFraction(progress: JobProgress): number {
  const [done, total] = progress.phase === "training" ? [progress.epochs_completed, progress.epochs] : [progress.evaluations, progress.budget]
  return total > 0 ? Math.min(1, Math.max(0, done / total)) : 0
}

export function progressLabel(progress: JobProgress): string {
  if (progress.phase === "training") return `Epoch ${progress.epochs_completed} of ${progress.epochs}`
  const best = progress.best_validation_accuracy
  return `${progress.evaluations} of ${progress.budget} evaluations${best != null ? ` · best validation ${best.toFixed(2)}%` : ""}`
}
