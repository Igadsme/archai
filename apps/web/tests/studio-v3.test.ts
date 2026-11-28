import { describe, expect, it } from "vitest"
import { contentSecurityPolicy, legacyRedirects } from "../next.config.mjs"
import { ApiError, request, resolveApiBase } from "../app/lib/api"
import { buildGraphModel, diffArchitectures } from "../app/lib/architectureGraph"
import { defaultConstraintForm } from "../app/lib/forms"
import type { FullArchitecture, ModelItem } from "../app/lib/types"
import { architectureDetailResponse, compareResponse, generateResponse, healthResponse, itemsResponse } from "../app/lib/validators"
import { normalizeMetrics } from "../app/screens/Benchmarks"
import { filterJobs } from "../app/screens/Experiments"
import { buildDiagnostics } from "../app/screens/Explorer"
import { buildGenerateRequest, GENERATABLE_OPS } from "../app/screens/Generator"
import { integrityLabel } from "../app/screens/Registry"
import { bestSoFarSeries } from "../app/screens/SearchLab"
import { serviceRows } from "../app/screens/System"
import { trainingCurve } from "../app/screens/Training"
import { filterCommands, navigationCommands } from "../app/studio/CommandPalette"
import { hrefFor, LEGACY_REDIRECTS, SCREENS, screenForPath } from "../app/studio/navigation"

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })

describe("typed API client", () => {
  it("sends the API key header and parses JSON", async () => {
    let seen: { url: string; headers: Record<string, string> } | null = null
    const fetchImpl = (async (url: string, init: RequestInit) => { seen = { url, headers: init.headers as Record<string, string> }; return json(200, { status: "ok" }) }) as unknown as typeof fetch
    const result = await request<{ status: string }>("/health", { fetchImpl, baseUrl: "http://api.test", apiKey: "k-123", validate: healthResponse })
    expect(result.ok && result.data.status).toBe("ok")
    expect(seen!.url).toBe("http://api.test/health")
    expect(seen!.headers["x-api-key"]).toBe("k-123")
  })

  it("omits the key header when no key is set", async () => {
    let headers: Record<string, string> = {}
    const fetchImpl = (async (_url: string, init: RequestInit) => { headers = init.headers as Record<string, string>; return json(200, { items: [] }) }) as unknown as typeof fetch
    await request("/v1/jobs", { fetchImpl, baseUrl: "http://api.test", apiKey: "" })
    expect(headers).not.toHaveProperty("x-api-key")
  })

  it("reports HTTP errors with the API detail and status", async () => {
    const fetchImpl = (async () => json(503, { detail: "generator checkpoint is not configured" })) as unknown as typeof fetch
    const result = await request("/v1/architectures/generate", { method: "POST", body: {}, fetchImpl, baseUrl: "http://api.test", apiKey: "" })
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.error.kind).toBe("http")
    expect(result.error.unavailable).toBe(true)
    expect(result.detail).toBe("generator checkpoint is not configured")
  })

  it("flags 401/403 as unauthorized", () => {
    expect(new ApiError("http", 401, "missing key").unauthorized).toBe(true)
    expect(new ApiError("http", 404, "nope").unauthorized).toBe(false)
  })

  it("times out a request that never answers", async () => {
    const fetchImpl = ((_url: string, init: RequestInit) => new Promise((_resolve, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))) as unknown as typeof fetch
    const result = await request("/v1/jobs", { fetchImpl, baseUrl: "http://api.test", apiKey: "", timeoutMs: 20 })
    expect(!result.ok && result.error.kind).toBe("timeout")
  })

  it("honours caller cancellation", async () => {
    const controller = new AbortController()
    const fetchImpl = ((_url: string, init: RequestInit) => new Promise((_resolve, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))) as unknown as typeof fetch
    const pending = request("/v1/jobs", { fetchImpl, baseUrl: "http://api.test", apiKey: "", signal: controller.signal })
    controller.abort()
    const result = await pending
    expect(!result.ok && result.error.kind).toBe("aborted")
  })

  it("reports network failures and invalid responses explicitly", async () => {
    const down = (async () => { throw new TypeError("fetch failed") }) as unknown as typeof fetch
    const offline = await request("/health", { fetchImpl: down, baseUrl: "http://api.test", apiKey: "" })
    expect(!offline.ok && offline.error.kind).toBe("network")
    const wrong = (async () => json(200, { unexpected: true })) as unknown as typeof fetch
    const invalid = await request("/v1/jobs", { fetchImpl: wrong, baseUrl: "http://api.test", apiKey: "", validate: itemsResponse })
    expect(!invalid.ok && invalid.error.kind).toBe("invalid_response")
  })

  it("resolves the API base URL from the environment value", () => {
    expect(resolveApiBase(undefined)).toBe("http://127.0.0.1:8000")
    expect(resolveApiBase("")).toBe("http://127.0.0.1:8000")
    expect(resolveApiBase("https://api.example.org/")).toBe("https://api.example.org")
  })
})

describe("response validators", () => {
  it("accept real shapes and reject wrong ones", () => {
    expect(healthResponse({ status: "ok", evidence_policy: "no fabricated metrics" })).toBeNull()
    expect(healthResponse({ ok: true })).not.toBeNull()
    expect(itemsResponse({ items: [] })).toBeNull()
    expect(itemsResponse([])).not.toBeNull()
    const arch = { nodes: [{ id: "input", op: "input", channels: 3 }], edges: [], input_spec: { channels: 3, height: 8, width: 8 }, output_classes: 10 }
    expect(architectureDetailResponse({ architecture: arch, hash: "a".repeat(24), analytical_metrics: { parameters: 0, flops: 0, activation_memory_bytes: 0 } })).toBeNull()
    expect(architectureDetailResponse({ architecture: arch, hash: "x" })).not.toBeNull()
    expect(compareResponse({ items: [] })).toBeNull()
    expect(generateResponse({ items: "no" })).not.toBeNull()
  })
})

// Expected totals come from POST /v1/architectures/validate on the live API (archai_compiler.metrics).
const fanIn: FullArchitecture = {
  nodes: [{ id: "input", op: "input", channels: 3 }, { id: "stem", op: "conv3x3", channels: 16 }, { id: "b1", op: "conv3x3", channels: 16 }, { id: "b2", op: "conv1x1", channels: 16 }, { id: "pool", op: "avg_pool3x3", channels: 16 }, { id: "output", op: "output", channels: 16 }],
  edges: [{ source: "input", target: "stem" }, { source: "stem", target: "b1" }, { source: "stem", target: "b2" }, { source: "b1", target: "pool" }, { source: "b2", target: "pool" }, { source: "stem", target: "output" }, { source: "pool", target: "output" }],
  input_spec: { channels: 3, height: 32, width: 32 }, output_classes: 10,
}
const kernel5: FullArchitecture = {
  nodes: [{ id: "input", op: "input", channels: 3 }, { id: "c1", op: "conv3x3", channels: 24, kernel_size: 5 }, { id: "s", op: "skip", channels: 24 }, { id: "c3", op: "conv1x1", channels: 32 }, { id: "output", op: "output", channels: 32 }],
  edges: [{ source: "input", target: "c1" }, { source: "c1", target: "s" }, { source: "s", target: "c3" }, { source: "c1", target: "c3" }, { source: "c3", target: "output" }],
  input_spec: { channels: 3, height: 16, width: 8 }, output_classes: 10,
} as FullArchitecture

describe("graph model built from typed architecture data", () => {
  it("per-node analytical costs sum to the backend totals", () => {
    expect(buildGraphModel(fanIn).totals).toEqual({ parameters: 3040, flops: 6275072, activationMemoryBytes: 65536 })
    expect(buildGraphModel(kernel5).totals).toEqual({ parameters: 2624, flops: 657408, activationMemoryBytes: 16384 })
  })

  it("lays out layers, shapes and edge kinds from the DAG", () => {
    const model = buildGraphModel(fanIn)
    expect(model.nodes.map((node) => [node.id, node.layer])).toEqual([["input", 0], ["stem", 1], ["b1", 2], ["b2", 2], ["pool", 3], ["output", 4]])
    expect(model.nodes.find((node) => node.id === "pool")!.outputShape).toEqual([16, 32, 32])
    const kind = (source: string, target: string) => model.edges.find((edge) => edge.source === source && edge.target === target)!.kind
    expect(kind("stem", "output")).toBe("residual")
    expect(kind("stem", "b1")).toBe("branch")
    expect(kind("input", "stem")).toBe("data")
    expect(model.residualCount).toBe(1)
    expect(new Set(model.nodes.map((node) => `${node.x},${node.y}`)).size).toBe(model.nodes.length)
  })

  it("diffs two architectures by node id, op and edges", () => {
    const diff = diffArchitectures(fanIn, { ...fanIn, nodes: fanIn.nodes.map((node) => node.id === "b2" ? { ...node, op: "conv3x3" } : node).concat([{ id: "extra", op: "skip", channels: 16 }]) })
    expect(diff).toEqual({ added: ["extra"], removed: [], changed: ["b2"], edgeDelta: 0 })
  })
})

describe("navigation", () => {
  it("routes every one of the ten screens", () => {
    expect(SCREENS).toHaveLength(10)
    expect(screenForPath("/")).toMatchObject({ id: "overview" })
    expect(screenForPath("/explorer/")).toMatchObject({ id: "explorer" })
    expect(screenForPath("/unknown").id).toBe("overview")
    expect(hrefFor("system")).toBe("/system")
    expect(navigationCommands(() => undefined)).toHaveLength(10)
  })

  it("keeps the legacy redirects in sync with next.config.mjs", () => {
    expect(legacyRedirects).toEqual(LEGACY_REDIRECTS)
  })

  it("keeps the strict CSP: self-hosted fonts, API-only connect-src, no framing", () => {
    expect(contentSecurityPolicy).toContain("font-src 'self'")
    expect(contentSecurityPolicy).toContain("frame-ancestors 'none'")
    expect(contentSecurityPolicy).not.toContain("fonts.googleapis.com")
    expect(contentSecurityPolicy).toMatch(/connect-src 'self' https?:\/\/[^ ;]+/)
  })

  it("filters commands by label, detail and group", () => {
    const commands = navigationCommands(() => undefined)
    expect(filterCommands(commands, "pareto").map((command) => command.id)).toEqual(["go-pareto"])
    expect(filterCommands(commands, "  ")).toHaveLength(10)
  })
})

describe("generator request", () => {
  const form = { count: "4", seed: "0", channels: "3", height: "32", width: "32", classes: "10", ...defaultConstraintForm }
  it("sends allowed_ops only when the vocabulary is narrowed", () => {
    const all = buildGenerateRequest(form, GENERATABLE_OPS.map((item) => item.op), "proj-1234")
    expect(all).toEqual({ ok: true, value: { count: 4, seed: 0, input_spec: { channels: 3, height: 32, width: 32 }, output_classes: 10, project_id: "proj-1234" } })
    const narrowed = buildGenerateRequest(form, ["conv3x3", "skip"])
    expect(narrowed.ok && narrowed.value.constraints).toEqual({ allowed_ops: ["conv3x3", "skip"] })
  })
  it("rejects out-of-range inputs and an empty vocabulary", () => {
    const result = buildGenerateRequest({ ...form, count: "65", classes: "1" }, [])
    expect(result.ok).toBe(false)
    expect(!result.ok && result.errors).toEqual(["candidates must be an integer in [1, 64]", "output classes must be an integer in [2, 10000]", "select at least one operation"])
  })
})

describe("explorer diagnostics", () => {
  const model = buildGraphModel(fanIn)
  it("never claims latency or trained weights", () => {
    const diagnostics = buildDiagnostics({ id: "a", draft: false, status: "ready", validation: { status: "pass" } }, model, true, true, null)
    expect(diagnostics.filter((item) => item.level === "FAIL")).toEqual([])
    expect(diagnostics.map((item) => item.code)).toEqual(expect.arrayContaining(["W_NO_LATENCY", "W_NO_WEIGHTS"]))
  })
  it("reports rejected graphs, offline validators and hash mismatches", () => {
    expect(buildDiagnostics({ id: "a", draft: false, status: "ready", validation: { status: "fail", error: "cycle" } }, model, true, true, null)[0]).toMatchObject({ level: "FAIL", code: "E_INVALID" })
    expect(buildDiagnostics({ id: "a", draft: false, status: "ready", validation: { status: "offline", error: "down" } }, model, true, true, null)[0]).toMatchObject({ level: "WARN", code: "W_OFFLINE" })
    expect(buildDiagnostics({ id: "a", draft: false, status: "ready", validation: { status: "pass" } }, model, false, false, null).some((item) => item.level === "FAIL")).toBe(true)
  })
})

describe("screen helpers use only measured values", () => {
  it("best-so-far series is monotone over the worker history", () => {
    expect(bestSoFarSeries([{ step: 1, index: 3, validation_accuracy: 80 }, { step: 2, index: 9, validation_accuracy: 75 }, { step: 3, index: 1, validation_accuracy: 88 }]).map((point) => point.best)).toEqual([80, 80, 88])
  })

  it("training curve comes from the stored result, else live progress, else nothing", () => {
    expect(trainingCurve({ job_id: "j", kind: "training", status: "succeeded", error: null, payload: { result: { history: [{ train_loss: 2.5, val_loss: 2.3 }] } } })).toEqual([{ epoch: 1, train_loss: 2.5, val_loss: 2.3 }])
    expect(trainingCurve({ job_id: "j", kind: "generator_training", status: "succeeded", error: null, payload: { result: { training_loss: [1.2, 0.9] } } })).toEqual([{ epoch: 1, training_loss: 1.2 }, { epoch: 2, training_loss: 0.9 }])
    expect(trainingCurve({ job_id: "j", kind: "training", status: "queued", error: null, payload: {} })).toEqual([])
  })

  it("filters jobs by status and text", () => {
    const jobs = [{ job_id: "aaa", kind: "search", status: "failed", error: "boom" }, { job_id: "bbb", kind: "training", status: "running", error: null }, { job_id: "ccc", kind: "training", status: "succeeded", error: null }]
    expect(filterJobs(jobs, "failed", "").map((job) => job.job_id)).toEqual(["aaa"])
    expect(filterJobs(jobs, "active", "").map((job) => job.job_id)).toEqual(["bbb"])
    expect(filterJobs(jobs, "all", "training").map((job) => job.job_id)).toEqual(["bbb", "ccc"])
    expect(filterJobs(jobs, "all", "boom").map((job) => job.job_id)).toEqual(["aaa"])
  })

  it("labels checkpoint integrity from the API flags", () => {
    const base: ModelItem = { model_id: "m", kind: "generator", version: "1", sha256: "0".repeat(64) }
    expect(integrityLabel({ ...base, integrity_verified: true }).text).toBe("SHA-256 VERIFIED")
    expect(integrityLabel({ ...base, integrity_verified: false, artifact_exists: false }).text).toBe("FILE MISSING")
    expect(integrityLabel({ ...base, integrity_verified: false, artifact_exists: true }).text).toBe("CHECKSUM MISMATCH")
    expect(integrityLabel(base).text).toBe("NOT CHECKED")
  })

  it("normalizes compared metrics against the largest value and marks the smallest", () => {
    const item = (id: string, parameters: number) => ({ architecture_id: id, architecture: fanIn, analytical_metrics: { parameters, flops: parameters * 10, activation_memory_bytes: 64 } })
    const [params] = normalizeMetrics([item("a", 100), item("b", 400)])
    expect(params.rows).toEqual([{ id: "a", value: 100, fraction: 0.25, best: true }, { id: "b", value: 400, fraction: 1, best: false }])
  })

  it("service rows reflect /health and /readiness, unknown when not loaded", () => {
    expect(serviceRows(null, null, null).every((row) => row.ok === null)).toBe(true)
    expect(serviceRows(null, null, "API unreachable")[0]).toMatchObject({ state: "DOWN", ok: false })
    const rows = serviceRows({ status: "ok" }, { status: "ready", durable_worker_configured: true, database_configured: true, database_ready: false }, null)
    expect(rows.map((row) => row.ok)).toEqual([true, false, true, true])
  })
})

describe("generator checkpoint label", () => {
  it("reports the checkpoint's own label or scale and nothing more", async () => {
    const { checkpointLabel } = await import("../app/screens/Generator")
    expect(checkpointLabel({ label: "fixture-only", scale: "ci_fixture" })).toBe("fixture-only")
    expect(checkpointLabel({ scale: "local_cpu" })).toBe("scale: local_cpu")
    expect(checkpointLabel({})).toBe("no label in checkpoint metadata")
  })
})
