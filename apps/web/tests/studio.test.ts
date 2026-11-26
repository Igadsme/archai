import { describe, expect, it } from "vitest"
import paretoFixture from "../app/lib/fixtures/pareto.json"
import fixtures from "../app/lib/fixtures/requests.json"
import { PAGES } from "../app/components/Shell"
import { SEARCH_ALGORITHMS } from "../app/lib/forms"
import { layoutDag } from "../app/lib/graph"
import { historyPoints, hypervolume, paretoFront } from "../app/lib/pareto"
import { ci, separated, splitAblations } from "../app/lib/results"
import type { ParetoPoint, ResearchResult, SeedSummary } from "../app/lib/types"

describe("Studio pages", () => {
  it("are exactly the ten pages named in docs/SPEC_ACCEPTANCE.md", () => {
    expect(PAGES.map((page) => page.label)).toEqual(["Research Dashboard", "Architecture Generator", "Architecture Graph Explorer", "Autonomous Search Laboratory",
      "Pareto Optimization Explorer", "Training Laboratory", "Model Comparison", "Research Results", "Model Registry", "System Administration"])
    expect(new Set(PAGES.map((page) => page.href)).size).toBe(10)
  })
})

describe("search policy list", () => {
  it("matches the backend policy registry (shared fixture checked by pytest too)", () => {
    expect([...SEARCH_ALGORITHMS]).toEqual(fixtures.algorithms)
  })
})

describe("pareto", () => {
  const points = paretoFixture.points as ParetoPoint[]
  it("keeps only non-dominated points sorted by params", () => {
    expect(paretoFront(points).map((p) => p.index)).toEqual([5, 0, 1, 3, 4])
  })
  it("computes the same hypervolume as archai_benchmark.hypervolume_2d", () => {
    expect(hypervolume(points, paretoFixture.reference as [number, number])).toBeCloseTo(paretoFixture.hypervolume, 9)
  })
  it("ignores history steps without a parameter cost", () => {
    expect(historyPoints([{ step: 1, index: 3, validation_accuracy: 80 }, { step: 2, index: 4, validation_accuracy: 81, params_m: 0.3 }])).toEqual(
      [{ index: 4, architecture_string: undefined, validation_accuracy: 81, params_m: 0.3 }])
  })
})

describe("layoutDag", () => {
  it("places nodes on longest-path layers", () => {
    const layout = layoutDag(["input", "a", "b", "output"], [
      { source: "input", target: "a" }, { source: "input", target: "b" }, { source: "a", target: "b" }, { source: "b", target: "output" }])
    expect(Object.fromEntries(layout.nodes.map((node) => [node.id, node.layer]))).toEqual({ input: 0, a: 1, b: 2, output: 3 })
    expect(layout.width).toBeGreaterThan(0)
  })
  it("stacks siblings in the same layer and rejects cycles", () => {
    const layout = layoutDag(["s", "x", "y"], [{ source: "s", target: "x" }, { source: "s", target: "y" }])
    expect(layout.nodes.filter((node) => node.layer === 1).map((node) => node.row)).toEqual([0, 1])
    expect(() => layoutDag(["p", "q"], [{ source: "p", target: "q" }, { source: "q", target: "p" }])).toThrow(/cycle/)
  })
})

describe("result helpers", () => {
  const s = (mean: number, low: number, high: number): SeedSummary => ({ mean, ci_low: low, ci_high: high, std: 0, n_seeds: 10 })
  const result = { name: "x", report: { algorithms: {
    random: { runs: 10, best_validation_accuracy: s(91.0, 90.9, 91.1) }, bayesian: { runs: 10, best_validation_accuracy: s(91.6, 91.5, 91.7) },
    bayesian_no_uncertainty: { runs: 10, best_validation_accuracy: s(91.5, 91.3, 91.6) } } },
    experiment: { name: "x", budget: 100, seeds: [0], algorithms: ["random", "bayesian"], ablations: [{ name: "bayesian_no_uncertainty", algorithm: "bayesian", params: {} }] } } as ResearchResult
  it("separates ablations using the committed experiment config", () => {
    expect(splitAblations(result)).toEqual({ policies: ["bayesian", "random"], ablations: ["bayesian_no_uncertainty"] })
  })
  it("formats CIs and flags only non-overlapping intervals", () => {
    expect(ci(s(1, 0.5, 1.5))).toBe("1.00 [0.50, 1.50]")
    expect(ci(undefined)).toBe("—")
    expect(separated(s(91.6, 91.5, 91.7), s(91.0, 90.9, 91.1))).toBe(true)
    expect(separated(s(91.2, 91.0, 91.4), s(91.0, 90.9, 91.1))).toBe(false)
  })
})
