// Browser end-to-end check of the ten ArchAI Studio V3 screens against a live stack (API + worker + a benchmark).
// Locally this uses the official NATS-Bench archive. In GitHub Actions it uses the committed
// 256-cell fixture at datasets/fixtures/natsbench-tss-cifar10-256 (fixture-only, not a research result)
// with ARCHAI_E2E_INDICES=0:256 and ARCHAI_E2E_BUDGET=8. Usage:
//   ARCHAI_E2E_API_KEY_FILE=/path/to/key CHROME=/usr/bin/google-chrome SCREENS=/tmp/screens node e2e/studio.e2e.mjs
// The key is read from a file and typed into the Studio key field; it is never logged.
// If CHROME is unset, Playwright uses chromium.executablePath() (CI installs Chromium this way).
import { readFileSync, mkdirSync, statSync } from "node:fs"
import { chromium } from "playwright-core"

const STUDIO = process.env.STUDIO_URL ?? "http://127.0.0.1:3000"
const API = process.env.API_URL ?? "http://127.0.0.1:8000"
const SCREENS = process.env.SCREENS ?? "/tmp/archai-screens"
const KEY = readFileSync(process.env.ARCHAI_E2E_API_KEY_FILE, "utf8").trim()
const CHECKPOINT = process.env.ARCHAI_E2E_CHECKPOINT // optional: a checkpoint to register and inspect
export const SCREEN_ROUTES = [["/", "overview", "Research Overview"], ["/explorer", "explorer", "Neural Architecture Explorer"], ["/generator", "generator", "Architecture Generator"],
  ["/search", "search", "Autonomous Search Laboratory"], ["/training", "training", "Training and GPU Monitoring"], ["/pareto", "pareto", "Pareto Optimization Explorer"],
  ["/benchmarks", "benchmarks", "Benchmark Comparison"], ["/experiments", "experiments", "Experiment History"], ["/registry", "registry", "Model Registry"], ["/system", "system", "System Administration"]]
const VIEWPORTS = (process.env.ARCHAI_E2E_VIEWPORTS ?? "1920x1080,1440x900,1280x800,1024x768,768x1024").split(",").map((value) => { const [width, height] = value.split("x").map(Number); return { width, height } })
mkdirSync(SCREENS, { recursive: true })
const results = []
// Never let the key reach logs: Playwright errors can echo DOM values (the key field), so redact everything printed.
const redact = (text) => String(text).split(KEY).join("<redacted>")
for (const stream of [process.stdout, process.stderr]) { const write = stream.write.bind(stream); stream.write = (chunk, ...rest) => write(redact(chunk), ...rest) }
process.on("uncaughtException", (error) => { console.error(redact(error?.stack ?? error)); process.exit(2) })
process.on("unhandledRejection", (error) => { console.error(redact(error?.stack ?? error)); process.exit(2) })
const check = (name, ok, detail = "") => { results.push({ name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`) }
const until = async (fn, ms = 120000, step = 1500) => { const end = Date.now() + ms; while (Date.now() < end) { if (await fn()) return true; await new Promise((r) => setTimeout(r, step)) } return false }

if (CHECKPOINT) {
  const response = await fetch(`${API}/v1/models`, { method: "POST", headers: { "content-type": "application/json", "x-api-key": KEY },
    body: JSON.stringify({ model_id: "archai-v1-generator-e2e", kind: "generator", version: `e2e-${statSync(CHECKPOINT).mtimeMs | 0}`, artifact_path: CHECKPOINT, metadata: { scale: "ci_fixture", label: "fixture-only" } }) })
  check("setup: register a checkpoint via API", response.ok || response.status === 409, `HTTP ${response.status}`)
}

const SEARCH_BUDGET = Number(process.env.ARCHAI_E2E_BUDGET ?? "20")
const SEARCH_INDICES = process.env.ARCHAI_E2E_INDICES ?? "0:15625"
const chromePath = process.env.CHROME || chromium.executablePath()
const browser = await chromium.launch({ executablePath: chromePath, args: ["--no-sandbox"] })
const consoleErrors = []
async function newPage(viewport) {
  const context = await browser.newContext({ viewport, acceptDownloads: true })
  const page = await context.newPage()
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(`${viewport.width}x${viewport.height} ${page.url()}: ${message.text()} ${message.location()?.url ?? ""}`) })
  page.on("pageerror", (error) => consoleErrors.push(`${viewport.width}x${viewport.height} ${page.url()}: ${error.message}`))
  await page.goto(`${STUDIO}/`)
  const key = page.getByLabel(/API key \(kept/)
  if (await key.isVisible()) await key.fill(KEY)
  else { await page.getByRole("button", { name: "API key", exact: true }).click(); const popover = page.getByRole("dialog", { name: "API key" }); await popover.getByLabel(/API key \(kept/).fill(KEY); await popover.getByRole("button", { name: "Done" }).click() }
  return page
}
const noLoadErrors = async (page) => (await page.getByText(/^Could not load/).count()) === 0
const visit = async (page, href) => { await page.goto(`${STUDIO}${href}`); await page.waitForLoadState("networkidle"); await page.waitForTimeout(400) }

// ---- live flows at 1440x900 ----
const desk = await newPage({ width: 1440, height: 900 })

// Overview: create a research project and keep it selected.
await visit(desk, "/")
const projectName = `E2E project ${Date.now()}`
await desk.locator('form[aria-label="Create research project"]').getByLabel(/^Name$/).fill(projectName)
await desk.getByRole("button", { name: "Create project" }).click()
const projectCreated = await until(async () => (await desk.getByText(`Created ${projectName}`).count()) > 0, 15000, 500)
const projectPressed = projectCreated ? await desk.getByRole("button", { name: `Select ${projectName}` }).getAttribute("aria-pressed") : "false"
const sidebarProject = await until(async () => (await desk.getByLabel("Research project").locator("option:checked").innerText()) === projectName, 10000, 500)
check("overview: create a research project; it is selected here and in the sidebar", projectCreated && projectPressed === "true" && sidebarProject, `created=${projectCreated} pressed=${projectPressed} sidebar=${sidebarProject}`)

// Command palette: Ctrl+K, filter, Enter navigates.
await desk.keyboard.press("Control+k")
await desk.getByRole("dialog", { name: "Command palette" }).getByLabel("Search commands").fill("pareto")
await desk.keyboard.press("Enter")
check("command palette: Ctrl+K → 'pareto' → Enter opens the Pareto explorer", await until(async () => new URL(desk.url()).pathname === "/pareto", 10000, 300), desk.url())

// Search laboratory: launch a multi-objective search and watch it finish on the worker.
await visit(desk, "/search")
await desk.getByLabel("Policy").selectOption("multi_objective")
await desk.getByLabel(/^Budget/).fill(String(SEARCH_BUDGET)); await desk.getByLabel(/^Seed/).fill("4"); await desk.getByLabel(/indices/).fill(SEARCH_INDICES)
await desk.getByRole("button", { name: "Launch search" }).click()
const queued = await until(async () => (await desk.getByText(/^Queued search/).count()) > 0, 15000, 500)
const historyRows = desk.locator('table[aria-label="Search history"] tbody tr')
const finished = queued && await until(async () => (await historyRows.count()) === SEARCH_BUDGET, 180000)
const chart = await desk.locator('[aria-label="Validation accuracy per evaluation and best so far"] svg').count()
check(`search lab: multi_objective search runs on the worker; ${SEARCH_BUDGET} history steps, convergence chart and population board`, finished && chart === 1 && (await desk.locator(".population-grid button").count()) === SEARCH_BUDGET,
  `queued=${queued} rows=${await historyRows.count()} chart=${chart}`)

// Pareto explorer: measured fronts + the live session's front.
await visit(desk, "/pareto")
const suiteChart = await until(async () => (await desk.locator(".scatter svg").count()) >= 1, 15000, 500)
await desk.locator('section[aria-label="Live search session"] select').selectOption({ index: 1 })
const liveText = await until(async () => (await desk.getByText(/evaluated · front size \d+ · hypervolume/).count()) > 0, 15000, 500)
await desk.locator(".selectable-dot").first().focus(); await desk.keyboard.press("Enter")
const detail = await desk.locator('section[aria-label="Candidate detail"]').innerText()
check("pareto explorer: measured-suite fronts, candidate detail and live-session front render", suiteChart && liveText && /CELL \d+/.test(detail), `charts=${await desk.locator(".scatter svg").count()}`)

// Explorer: validate and register the default spec, check the graph, use keyboard + resize, export JSON + TorchScript.
await visit(desk, "/explorer")
await desk.getByRole("tab", { name: "SPEC EDITOR" }).click()
await desk.getByRole("button", { name: "Validate and register" }).click()
const registered = await until(async () => (await desk.getByText(/^Registered [0-9a-f]{12}/).count()) > 0 || (await desk.getByText(/already registered/).count()) > 0, 20000, 500)
const drawn = await until(async () => (await desk.locator(".graph-node-advanced").count()) >= 3, 15000, 500)
const validPill = await until(async () => (await desk.getByText("GRAPH VALID").count()) > 0, 15000, 500)
const zoomBefore = await desk.locator('code[aria-live="polite"]').first().innerText()
await desk.locator(".advanced-canvas").click({ position: { x: 20, y: 20 } }); await desk.keyboard.press("+")
const zoomAfter = await desk.locator('code[aria-live="polite"]').first().innerText()
const inspectorBox = await desk.locator(".technical-inspector").boundingBox()
await desk.getByRole("separator", { name: "Resize inspector" }).focus()
for (let i = 0; i < 4; i += 1) await desk.keyboard.press("ArrowLeft")
const inspectorAfter = await desk.locator(".technical-inspector").boundingBox()
await desk.locator(".graph-node-advanced").nth(1).click()
const operatorTab = await desk.getByText("TENSOR CONTRACT").count()
await desk.getByRole("tab", { name: "GRAPH", exact: true }).click()
const [jsonDownload] = await Promise.all([desk.waitForEvent("download"), desk.getByRole("button", { name: "Export JSON" }).click()])
const [ptDownload] = await Promise.all([desk.waitForEvent("download", { timeout: 60000 }), desk.getByRole("button", { name: /Export PyTorch/ }).click()])
const ptPath = `${SCREENS}/export-${ptDownload.suggestedFilename()}`; await ptDownload.saveAs(ptPath)
await jsonDownload.saveAs(`${SCREENS}/export-${jsonDownload.suggestedFilename()}`)
const [graphExport] = await Promise.all([desk.waitForEvent("download"), desk.getByRole("button", { name: "Export graph" }).click()])
const graphPath = `${SCREENS}/export-${graphExport.suggestedFilename()}`; await graphExport.saveAs(graphPath)
const graphJson = JSON.parse(readFileSync(graphPath, "utf8"))
check("explorer: register via API, graph renders from the registry, API validation pill passes", registered && drawn && validPill, `registered=${registered} nodes=${await desk.locator(".graph-node-advanced").count()}`)
check("explorer: '+' zooms, inspector resizes with the keyboard, node selection opens the operator inspector", zoomBefore !== zoomAfter && inspectorBox && inspectorAfter && inspectorAfter.width > inspectorBox.width && operatorTab > 0,
  `zoom ${zoomBefore}→${zoomAfter} inspector ${inspectorBox?.width}→${inspectorAfter?.width}`)
check("explorer: JSON, TorchScript and local graph exports download", statSync(ptPath).size > 0 && Array.isArray(graphJson?.architecture?.nodes ?? graphJson?.graph?.nodes ?? graphJson?.nodes),
  `pt=${ptDownload.suggestedFilename()} (${statSync(ptPath).size} bytes) graph=${graphExport.suggestedFilename()}`)
await desk.getByRole("button", { name: "Measure latency" }).click()
const latencyShown = await until(async () => /\d+\.\d\d ms/.test((await desk.locator(".workbench-kpis").textContent()) ?? ""), 60000, 500)
check("explorer: Measure latency stores a measured p50 on the API host and shows it", latencyShown, (await desk.locator(".workbench-kpis").textContent())?.match(/LATENCY[^]*?ms/)?.[0] ?? "")
console.log(`TORCHSCRIPT_EXPORT=${ptPath}`)

// Generator: generate, validate and save one candidate.
await visit(desk, "/generator")
check("generator: constraint inputs are available", await desk.getByLabel(/^Max parameters/).count() > 0)
await desk.getByRole("button", { name: "Generate candidates" }).last().click()
const generated = await until(async () => (await desk.getByRole("button", { name: "Save to registry" }).count()) > 0, 60000, 500)
const validated = generated && await until(async () => (await desk.getByText("VALID GRAPH").count()) > 0, 20000, 500)
if (generated) await desk.getByRole("button", { name: "Save to registry" }).first().click()
const saved = generated && await until(async () => (await desk.getByRole("button", { name: "Saved to registry" }).count()) > 0, 15000, 500)
check("generator: candidates generated from the checkpoint, validated by the API and one saved", generated && validated && saved, `generated=${generated} validated=${validated} saved=${saved}`)

// Benchmarks: policy table, compare two registered architectures, smoke result set.
await visit(desk, "/benchmarks")
const policyRows = await desk.locator('table[aria-label="Search policies at a matched budget"] tbody tr').count()
const boxes = desk.locator('.compare-list input[type="checkbox"]')
await boxes.nth(0).check(); await boxes.nth(1).check()
await desk.getByRole("button", { name: /^Compare 2 selected/ }).click()
const compared = await until(async () => (await desk.getByText("(fewest)").count()) > 0, 15000, 500)
check("benchmarks: policy table lists 7 policies + 4 ablations; 2 architectures compared", compared && policyRows === 11, `policyRows=${policyRows}`)
await desk.getByRole("button", { name: /archai_v1_smoke/ }).click()
check("benchmarks: smoke result set shows its predictor report", await until(async () => (await desk.getByText("Predictor report (smoke-scale)").count()) > 0, 10000, 500))

// Registry: architectures tab detail + checkpoint inspection.
await visit(desk, "/registry")
await desk.locator(".registry-list .link-button").first().click()
const archDetail = await until(async () => (await desk.getByRole("button", { name: "Open in explorer" }).count()) > 0, 10000, 500)
await desk.getByRole("tab", { name: /CHECKPOINTS/ }).click()
const inspectButtons = desk.getByRole("button", { name: "Inspect" })
if (await inspectButtons.count()) {
  await inspectButtons.last().click()
  const inspected = await until(async () => (await desk.locator('table[aria-label="Checkpoint tensors"] tbody tr').count()) > 0, 30000, 500)
  check("registry: architecture detail opens; checkpoint inspection lists tensors", archDetail && inspected, `tensors=${await desk.locator('table[aria-label="Checkpoint tensors"] tbody tr').count()}`)
} else check("registry: architecture detail opens; checkpoint inspection lists tensors", false, "no registered checkpoints")
await desk.getByRole("tab", { name: /DEPLOYMENTS/ }).click()
check("registry: deployments tab states there is no deployment endpoint", (await desk.getByText("No deployment endpoint").count()) > 0)

// Training: queue the default synthetic candidate job and read its measured curve.
await visit(desk, "/training")
await desk.getByRole("button", { name: "Queue job" }).click()
const trainingNotice = await until(async () => (await desk.getByText(/^Queued training job [0-9a-f]{8}/).count()) > 0, 15000, 500)
const jobShort = trainingNotice ? (await desk.getByText(/^Queued training job/).innerText()).match(/([0-9a-f]{8})/)?.[1] : null
const trained = !!jobShort && await until(async () => (await desk.locator(".job-row", { hasText: jobShort }).getByText("SUCCEEDED").count()) > 0, 180000)
check("training: synthetic candidate job succeeds and shows its measured curve; GPU telemetry shows live devices or states why there is no GPU",
  trained && (await until(async () => (await desk.locator('table[aria-label="Measured training curve"]').count()) > 0, 15000, 500)) && ((await desk.locator('table[aria-label="GPU telemetry"]').count()) > 0 || (await desk.getByText(/No GPU:/).count()) > 0), `job=${jobShort}`)

// Experiments: filter + deep link.
await visit(desk, "/experiments")
await desk.getByRole("button", { name: /^Failed only/ }).click()
const failedFilter = await desk.getByRole("button", { name: /^Failed only/ }).getAttribute("aria-pressed")
await desk.getByRole("button", { name: /^All/ }).click()
const anyJob = await desk.locator(".experiment-list > button").count()
check("experiments: jobs listed, 'Failed only' filter toggles, run detail shows a timeline", anyJob > 0 && failedFilter === "true" && (await desk.getByText("TIMELINE").count()) > 0, `jobs=${anyJob}`)
const cancelled = await (await fetch(`${API}/v1/training`, { method: "POST", headers: { "content-type": "application/json", "x-api-key": KEY }, body: JSON.stringify({ kind: "candidate", payload: { architecture: { nodes: [{ id: "input", op: "input", channels: 3 }, { id: "conv", op: "conv3x3", channels: 4 }, { id: "output", op: "output", channels: 4 }], edges: [{ source: "input", target: "conv" }, { source: "conv", target: "output" }], input_spec: { channels: 3, height: 8, width: 8 }, output_classes: 10 }, dataset: "synthetic", epochs: 200, train_samples: 2048 } }) })).json()
await fetch(`${API}/v1/jobs/${cancelled.job_id}/cancel`, { method: "POST", headers: { "x-api-key": KEY } })
await visit(desk, `/experiments?job=${cancelled.job_id}`)
const original = (await (await fetch(`${API}/v1/jobs/${cancelled.job_id}`)).json()).status
if (original === "cancelled") await desk.getByRole("button", { name: "Retry", exact: true }).click()
const retried = await until(async () => (await desk.getByRole("button", { name: "Open original" }).count()) > 0, 15000, 500)
const retriedAs = (await (await fetch(`${API}/v1/jobs/${cancelled.job_id}`)).json()).payload?.retried_as
check("experiments: Retry re-queues a cancelled job with the same inputs and links both runs", original === "cancelled" && retried && !!retriedAs, `original=${original} retried_as=${retriedAs?.slice(0, 8)}`)

// System: readiness, workers and the audit log (needs the key).
await visit(desk, "/system")
const ready = await until(async () => (await desk.getByText("READY", { exact: true }).count()) > 0, 10000, 500)
const audit = await until(async () => (await desk.locator('table[aria-label="Audit log"] tbody tr').count()) > 0, 15000, 500)
check("system: readiness ready, a live worker listed and the audit log shows write requests", ready && (await desk.locator(".worker-list > div").count()) > 0 && audit,
  `ready=${ready} audit=${audit}`)

// System: create a user, issue a read-only key in the Studio, and check the API accepts it (secret never printed).
const userEmail = `e2e-${Date.now()}@example.org`
await desk.getByRole("form", { name: "Create user" }).getByLabel("Email").fill(userEmail)
await desk.getByRole("button", { name: "Create user" }).click()
await until(async () => (await desk.getByRole("table", { name: "Users" }).getByText(userEmail).count()) > 0, 10000, 300)
const keyForm = desk.getByRole("form", { name: "Issue API key" })
await keyForm.getByLabel("Owner").selectOption({ label: `${userEmail} (member)` })
await keyForm.getByLabel("Key name").fill("e2e-read-only")
await keyForm.getByLabel("write").uncheck()
await desk.getByRole("button", { name: "Issue key" }).click()
const secretShown = await until(async () => (await desk.getByLabel("New API key secret").count()) > 0, 10000, 300)
const issuedSecret = secretShown ? (await desk.getByLabel("New API key secret").textContent())?.trim() : ""
const issuedWho = issuedSecret ? await (await fetch(`${API}/v1/auth/whoami`, { headers: { "x-api-key": issuedSecret } })).json() : null
const issuedWrite = issuedSecret ? (await fetch(`${API}/v1/projects`, { method: "POST", headers: { "content-type": "application/json", "x-api-key": issuedSecret }, body: JSON.stringify({ name: "denied", task: "t" }) })).status : 0
check("system: create a user and a read-only key; the key authenticates and cannot write", issuedWho?.principal?.email === userEmail && issuedWrite === 403,
  `scopes=${issuedWho?.principal?.scopes?.join("+")} write=${issuedWrite}`)
await desk.getByRole("button", { name: "Dismiss" }).click()

const archForExplorer = await (await fetch(`${API}/v1/architectures?limit=50`)).json()
const richest = archForExplorer.items?.sort((a, b) => b.metrics.parameters - a.metrics.parameters)[0]?.architecture_id
await desk.context().close()

// ---- every screen at every viewport: navigation, overflow, graph, data, unnamed controls ----
for (const viewport of VIEWPORTS) {
  const page = await newPage(viewport)
  const tag = `${viewport.width}x${viewport.height}`
  for (const [href, name, title] of SCREEN_ROUTES) {
    await visit(page, href === "/explorer" && richest ? `/explorer?id=${richest}` : href)
    if (href === "/explorer") await until(async () => (await page.locator(".graph-node-advanced").count()) > 0, 15000, 500)
    const active = await page.locator('nav a[aria-current="page"]').getAttribute("title")
    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main")
      const wide = [...document.querySelectorAll("main *")].filter((el) => { const box = el.getBoundingClientRect(); return box.width > 0 && box.right > window.innerWidth + 1 && !el.closest(".table-wrap,.document-tabs,.page-actions,.architecture-tree,.segmented,[class*=scroll]") }).length
      return { doc: document.documentElement.scrollWidth - window.innerWidth, main: main ? main.scrollWidth - main.clientWidth : 0, wide }
    })
    const unnamed = await page.locator("button:visible").evaluateAll((buttons) => buttons.filter((b) => !(b.textContent ?? "").trim() && !b.getAttribute("aria-label") && !b.getAttribute("title")).length)
    const graph = href === "/explorer" ? await page.locator(".graph-node-advanced").count() : null
    const ok = active === title && overflow.doc <= 1 && overflow.main <= 1 && overflow.wide === 0 && unnamed === 0 && await noLoadErrors(page) && (graph === null || graph > 0)
    check(`${tag} ${href}: nav marks "${title}", no horizontal overflow, data loads${graph === null ? "" : ", graph renders"}`, ok,
      `active="${active}" overflow=${JSON.stringify(overflow)} unnamed=${unnamed}${graph === null ? "" : ` nodes=${graph}`}`)
    await page.screenshot({ path: `${SCREENS}/${name}-${tag}.png` })
    if (href === "/explorer" && viewport.width > 800) {
      const before = await page.locator(".architecture-browser").boundingBox()
      await page.getByRole("separator", { name: "Resize architecture browser" }).focus()
      for (let i = 0; i < 3; i += 1) await page.keyboard.press("ArrowRight")
      const after = await page.locator(".architecture-browser").boundingBox()
      const consoleBefore = await page.locator(".pro-console").boundingBox()
      await page.getByRole("separator", { name: "Resize console" }).focus()
      for (let i = 0; i < 3; i += 1) await page.keyboard.press("ArrowUp")
      const consoleAfter = await page.locator(".pro-console").boundingBox()
      check(`${tag} explorer: browser and console panels resize`, before && after && after.width > before.width && consoleBefore && consoleAfter && consoleAfter.height > consoleBefore.height,
        `browser ${before?.width}→${after?.width} console ${consoleBefore?.height}→${consoleAfter?.height}`)
      await page.evaluate(() => { for (const key of Object.keys(localStorage)) if (["archai.explorer.left", "archai.explorer.right", "archai.explorer.console"].includes(key)) localStorage.removeItem(key) })
    }
  }
  await page.context().close()
}

await browser.close()
check("no browser console errors", consoleErrors.length === 0, consoleErrors.slice(0, 5).join(" | "))
const failed = results.filter((item) => !item.ok)
console.log(`SUMMARY ${results.length - failed.length}/${results.length} passed`)
process.exit(failed.length ? 1 : 0)
