import type { ExperimentItem } from "./types"

export type LeaderboardRow = { rank: number; experimentId: string; architectureId: string; evidenceType: string; validation: number; test: number | null }

/**
 * Rank completed or recorded experiments by validation accuracy only. Test accuracy is shown,
 * never used for ordering, and predicted evidence is kept apart from measured or benchmark evidence.
 */
export function buildLeaderboard(experiments: ExperimentItem[], evidenceTypes: string[] = ["benchmark_lookup", "measured_training"]): LeaderboardRow[] {
  return experiments
    .filter((item) => evidenceTypes.includes(item.evidence_type) && typeof item.metrics?.validation_accuracy === "number" && item.status !== "failed" && item.status !== "cancelled")
    .sort((left, right) => right.metrics.validation_accuracy - left.metrics.validation_accuracy || left.experiment_id.localeCompare(right.experiment_id))
    .map((item, index) => ({
      rank: index + 1, experimentId: item.experiment_id, architectureId: item.architecture_id, evidenceType: item.evidence_type,
      validation: item.metrics.validation_accuracy, test: typeof item.metrics.test_accuracy === "number" ? item.metrics.test_accuracy : null,
    }))
}
