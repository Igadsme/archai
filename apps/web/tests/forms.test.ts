import { describe, expect, it } from "vitest"
import fixtures from "../app/lib/fixtures/requests.json"
import { buildConstraints, buildProjectRequest, buildSearchRequest, buildTrainingRequest, defaultConstraintForm, defaultProjectForm, defaultSearchForm, defaultTrainingForm, parseIndices } from "../app/lib/forms"

describe("parseIndices", () => {
  it("expands ranges, de-duplicates and sorts", () => {
    expect(parseIndices("5, 0:3, 2")).toEqual({ ok: true, value: [0, 1, 2, 5] })
  })
  it("accepts an empty string as no explicit pool", () => {
    expect(parseIndices("  ")).toEqual({ ok: true, value: [] })
  })
  it("rejects malformed, reversed and oversized input", () => {
    expect(parseIndices("a").ok).toBe(false)
    expect(parseIndices("9:3").ok).toBe(false)
    expect(parseIndices("-1").ok).toBe(false)
    expect(parseIndices("0:20", 10).ok).toBe(false)
  })
})

describe("buildSearchRequest", () => {
  it("produces the shared API contract fixture", () => {
    const built = buildSearchRequest({ ...defaultSearchForm, budget: "10", seed: "3", indices: "0:8,10:13" })
    expect(built).toEqual({ ok: true, value: fixtures.search })
  })
  it("rejects unknown algorithms and non-positive budgets", () => {
    const built = buildSearchRequest({ ...defaultSearchForm, algorithm: "reinforcement", budget: "0" })
    expect(built.ok).toBe(false)
    if (!built.ok) expect(built.errors.length).toBe(2)
  })
  it("rejects a budget larger than the explicit pool", () => {
    expect(buildSearchRequest({ ...defaultSearchForm, budget: "5", indices: "0:2" }).ok).toBe(false)
  })
})

describe("buildTrainingRequest", () => {
  it("builds a synthetic smoke-scale candidate job from the defaults", () => {
    expect(buildTrainingRequest(defaultTrainingForm)).toEqual({ ok: true, value: fixtures.candidate })
  })
  it("builds generator and predictor jobs matching the fixtures", () => {
    expect(buildTrainingRequest({ ...defaultTrainingForm, kind: "generator", epochs: "2", seed: "1", corpusPath: "/tmp/corpus.jsonl", checkpointPath: "/tmp/generator.pt" }))
      .toEqual({ ok: true, value: fixtures.generator })
    expect(buildTrainingRequest({ ...defaultTrainingForm, kind: "predictor", benchmarkPath: "/tmp/nats", checkpointPath: "/tmp/predictor.pt", benchmarkSha256: "A".repeat(64), indices: "1:4" }))
      .toEqual({ ok: true, value: fixtures.predictor })
  })
  it("rejects bad JSON, relative paths, short checksums and tiny predictor pools", () => {
    expect(buildTrainingRequest({ ...defaultTrainingForm, architectureJson: "{" }).ok).toBe(false)
    expect(buildTrainingRequest({ ...defaultTrainingForm, kind: "generator", corpusPath: "corpus.jsonl" }).ok).toBe(false)
    const predictor = buildTrainingRequest({ ...defaultTrainingForm, kind: "predictor", benchmarkPath: "/tmp/nats", checkpointPath: "/tmp/predictor.pt", benchmarkSha256: "abc", indices: "1,2" })
    expect(predictor.ok).toBe(false)
    if (!predictor.ok) expect(predictor.errors).toEqual(["benchmark SHA-256 must be 64 hex characters", "predictor training needs at least three indices"])
    expect(buildTrainingRequest({ ...defaultTrainingForm, epochs: "1001" }).ok).toBe(false)
  })
})


describe("buildProjectRequest", () => {
  it("trims a valid project and rejects a blank name", () => {
    expect(buildProjectRequest({ ...defaultProjectForm, name: "  CIFAR search  " })).toEqual({ ok: true, value: { name: "CIFAR search", task: "cifar10", description: "" } })
    expect(buildProjectRequest(defaultProjectForm).ok).toBe(false)
  })
})

describe("buildSearchRequest project_id", () => {
  it("omits project_id unless a project is selected", () => {
    const without = buildSearchRequest({ ...defaultSearchForm, budget: "10", seed: "3", indices: "0:8,10:13" })
    expect(without).toEqual({ ok: true, value: fixtures.search })
    const withProject = buildSearchRequest({ ...defaultSearchForm, budget: "10", seed: "3", indices: "0:8,10:13", projectId: "project01abcdefgh" })
    expect(withProject.ok && "value" in withProject && withProject.value.project_id).toBe("project01abcdefgh")
  })
})


describe("buildConstraints", () => {
  it("omits empty constraints and parses raw counts", () => {
    expect(buildConstraints(defaultConstraintForm)).toEqual({ ok: true, value: undefined })
    expect(buildConstraints({ ...defaultConstraintForm, maxParameters: "800000", allowedOps: "skip_connect, none" })).toEqual({
      ok: true, value: { max_parameters: 800000, allowed_ops: ["skip_connect", "none"] },
    })
  })
  it("rejects unknown ops and non-positive budgets", () => {
    expect(buildConstraints({ ...defaultConstraintForm, maxParameters: "0" }).ok).toBe(false)
    expect(buildConstraints({ ...defaultConstraintForm, allowedOps: "quantum_gate" }).ok).toBe(false)
  })
})
