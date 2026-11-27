import { describe, expect, it } from "vitest"
import { buildLeaderboard } from "../app/lib/leaderboard"
import type { ExperimentItem } from "../app/lib/types"

const experiment = (id: string, evidence: string, status: string, metrics: Record<string, number>): ExperimentItem =>
  ({ experiment_id: id, architecture_id: `arch-${id}`, evidence_type: evidence, status, metrics } as ExperimentItem)

describe("buildLeaderboard", () => {
  const rows = buildLeaderboard([
    experiment("a", "benchmark_lookup", "completed", { validation_accuracy: 90, test_accuracy: 99 }),
    experiment("b", "measured_training", "completed", { validation_accuracy: 91, test_accuracy: 80 }),
    experiment("c", "predicted", "completed", { validation_accuracy: 99 }),
    experiment("d", "benchmark_lookup", "failed", { validation_accuracy: 98 }),
    experiment("e", "benchmark_lookup", "completed", { test_accuracy: 100 }),
    experiment("f", "benchmark_lookup", "running", { validation_accuracy: 90 }),
  ])
  it("ranks by validation accuracy, never by test accuracy", () => {
    expect(rows.map((row) => row.experimentId)).toEqual(["b", "a", "f"])
    expect(rows[0]).toMatchObject({ rank: 1, validation: 91, test: 80 })
  })
  it("excludes predicted, failed and validation-less evidence", () => {
    expect(rows.find((row) => ["c", "d", "e"].includes(row.experimentId))).toBeUndefined()
  })
  it("shows missing test accuracy as null", () => {
    expect(rows[2].test).toBeNull()
  })
})
