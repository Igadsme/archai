import { describe, expect, it } from "vitest"
import { jobProgress, progressFraction, progressLabel } from "../app/lib/progress"

describe("job progress", () => {
  it("reads per-epoch training progress written by the worker", () => {
    const progress = jobProgress({ payload: { progress: { phase: "training", epochs_completed: 2, epochs: 5, history: [{ epoch: 0, train_loss: 1.2 }, { epoch: 1, train_loss: 0.9 }] } } })
    expect(progress?.phase).toBe("training")
    expect(progressFraction(progress!)).toBeCloseTo(0.4)
    expect(progressLabel(progress!)).toBe("Epoch 2 of 5")
    expect(progress?.phase === "training" && progress.history.length).toBe(2)
  })

  it("reads search progress with the best validation accuracy so far", () => {
    const progress = jobProgress({ payload: { progress: { phase: "searching", evaluations: 25, budget: 100, best_validation_accuracy: 91.234 } } })
    expect(progressFraction(progress!)).toBeCloseTo(0.25)
    expect(progressLabel(progress!)).toBe("25 of 100 evaluations · best validation 91.23%")
  })

  it("ignores missing or malformed progress", () => {
    expect(jobProgress(null)).toBeNull()
    expect(jobProgress({ payload: {} })).toBeNull()
    expect(jobProgress({ payload: { progress: { phase: "training", epochs: "five" } } })).toBeNull()
    expect(jobProgress({ payload: { progress: { phase: "unknown" } } })).toBeNull()
  })

  it("clamps the fraction and tolerates a zero budget", () => {
    expect(progressFraction({ phase: "searching", evaluations: 5, budget: 0 })).toBe(0)
    expect(progressFraction({ phase: "searching", evaluations: 12, budget: 10 })).toBe(1)
  })
})
