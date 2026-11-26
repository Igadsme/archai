// Browser end-to-end check of the ten Studio pages against a LIVE local stack (API + worker + NATS-Bench).
// Not part of CI (needs the stack). Usage:
//   ARCHAI_E2E_API_KEY_FILE=/path/to/key CHROME=/usr/bin/google-chrome SCREENS=/tmp/screens node e2e/studio.e2e.mjs
// The key is read from a file and typed into the Studio key field; it is never logged.
import { readFileSync, mkdirSync, statSync } from "node:fs"
import { chromium } from "playwright-core"

const STUDIO = process.env.STUDIO_URL ?? "http://127.0.0.1:3000"
const API = process.env.API_URL ?? "http://127.0.0.1:8000"
const SCREENS = process.env.SCREENS ?? "/tmp/archai-screens"
const KEY = readFileSync(process.env.ARCHAI_E2E_API_KEY_FILE, "utf8").trim()
const CHECKPOINT = process.env.ARCHAI_E2E_CHECKPOINT // optional: a checkpoint to register and inspect
const PAGES = [["/", "Research Dashboard"], ["/generator", "Architecture Generator"], ["/explorer", "Architecture Graph Explorer"],
  ["/search", "Autonomous Search Laboratory"], ["/pareto", "Pareto Optimization Explorer"], ["/training", "Training Laboratory"],
  ["/compare", "Model Comparison"], ["/results", "Research Results"], ["/models", "Model Registry"], ["/admin", "System Administration"]]
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
    body: JSON.stringify({ model_id: "archai-v1-predictor-smoke", kind: "predictor", version: `e2e-${statSync(CHECKPOINT).mtimeMs | 0}`, artifact_path: CHECKPOINT, metadata: { scale: "smoke", source: "scripts/train_predictor (CPU)" } }) })
  check("setup: register smoke checkpoint via API", response.ok || response.status === 409, `HTTP ${response.status}`)
}

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] })
const consoleErrors = []
async function newPage(viewport) {
  const context = await browser.newContext({ viewport, acceptDownloads: true })
  const page = await context.newPage()
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(`${viewport.width}px ${page.url()}: ${message.text()}`) })
  page.on("pageerror", (error) => consoleErrors.push(`${viewport.width}px ${page.url()}: ${error.message}`))
  await page.goto(`${STUDIO}/`); await page.getByLabel(/API key/).fill(KEY)
  return page
}
const noLoadErrors = async (page) => (await page.getByText(/^Could not load/).count()) === 0

// ---- desktop: every page, then real flows ----
const desk = await newPage({ width: 1280, height: 900 })
for (const [href, title] of PAGES) {
  await desk.goto(`${STUDIO}${href}`); await desk.waitForLoadState("networkidle")
  const active = await desk.locator('nav a[aria-current="page"]').innerText()
  const unnamed = await desk.locator("button").evaluateAll((buttons) => buttons.filter((b) => !(b.textContent ?? "").trim() && !b.getAttribute("aria-label")).length)
  check(`desktop ${href}: nav marks "${title}", data loads, no unnamed buttons`, active === title && await noLoadErrors(desk) && unnamed === 0, `active="${active}" unnamed=${unnamed}`)
  await desk.screenshot({ path: `${SCREENS}/desktop${href === "/" ? "-dashboard" : href.replace("/", "-")}.png`, fullPage: true })
}

// E2E step 1: create a research project on the dashboard and keep it selected.
await desk.goto(`${STUDIO}/`); await desk.waitForLoadState("networkidle")
const projectName = `E2E project ${Date.now()}`
await desk.locator('form[aria-label="Create research project"]').getByLabel(/^Name$/).fill(projectName)
await desk.getByRole("button", { name: "Create project" }).click()
const projectCreated = await until(async () => (await desk.getByText(`Created ${projectName}`).count()) > 0, 15000, 500)
const projectPressed = projectCreated ? await desk.getByRole("button", { name: `Select ${projectName}` }).getAttribute("aria-pressed") : "false"
check("dashboard: create and select a research project (E2E step 1)", projectCreated && projectPressed === "true",
  `created=${projectCreated} pressed=${projectPressed}`)
await desk.screenshot({ path: `${SCREENS}/flow-project.png`, fullPage: true })

await desk.goto(`${STUDIO}/generator`); await desk.waitForLoadState("networkidle")
check("generator: constraint inputs are available",
  await desk.getByLabel("Max parameters").count() > 0 && await desk.getByText("constraint-conditioned generation in the Studio").count() === 0)

// Search laboratory: launch a multi-objective search and watch it finish.
await desk.goto(`${STUDIO}/search`); await desk.waitForLoadState("networkidle")
await desk.getByLabel("Policy").selectOption("multi_objective")
await desk.getByLabel(/^Budget/).fill("20"); await desk.getByLabel(/^Seed/).fill("4"); await desk.getByLabel(/indices/).fill("0:15625")
await desk.getByRole("button", { name: "Launch search" }).click()
const queued = await until(async () => (await desk.getByText(/^Queued search/).count()) > 0, 15000, 500)
const finished = queued && await until(async () => (await desk.getByText(/^multi_objective · succeeded/).count()) > 0)
const historyTable = desk.locator("table", { hasText: "Best so far" })
const stepRows = finished && await until(async () => (await historyTable.locator("tbody tr").count()) === 20, 20000, 500) ? 20 : await historyTable.locator("tbody tr").count()
check("search lab: multi_objective search runs on the worker and shows 20 history steps", finished && stepRows === 20, `queued=${queued} finished=${finished} rows=${stepRows}`)
await desk.screenshot({ path: `${SCREENS}/flow-search-session.png`, fullPage: true })

// Pareto explorer: measured fronts chart + the live session's front.
await desk.goto(`${STUDIO}/pareto`); await desk.waitForLoadState("networkidle")
const suiteChart = await desk.locator("figure.chart svg").count()
await desk.locator("article", { hasText: "Live search session" }).locator("select").selectOption({ index: 1 })
const liveText = await until(async () => (await desk.getByText(/evaluated · front size \d+ · hypervolume/).count()) > 0, 15000, 500)
check("pareto explorer: measured-suite chart and live-session front render", suiteChart >= 1 && liveText, `charts=${await desk.locator("figure.chart svg").count()}`)
await desk.screenshot({ path: `${SCREENS}/flow-pareto.png`, fullPage: true })

// Graph explorer: register, draw, export JSON + TorchScript.
await desk.goto(`${STUDIO}/explorer`); await desk.waitForLoadState("networkidle")
await desk.getByRole("button", { name: "Validate and register" }).click()
const drawn = await until(async () => (await desk.locator(".dag-scroll svg rect").count()) > 0, 15000, 500)
const [jsonDownload] = await Promise.all([desk.waitForEvent("download"), desk.getByRole("button", { name: "Export JSON" }).click()])
const [ptDownload] = await Promise.all([desk.waitForEvent("download", { timeout: 60000 }), desk.getByRole("button", { name: /Export PyTorch/ }).click()])
const ptPath = `${SCREENS}/export-${ptDownload.suggestedFilename()}`; await ptDownload.saveAs(ptPath)
await jsonDownload.saveAs(`${SCREENS}/export-${jsonDownload.suggestedFilename()}`)
check("graph explorer: DAG renders and JSON + TorchScript exports download", drawn && statSync(ptPath).size > 0, `pt=${ptDownload.suggestedFilename()} (${statSync(ptPath).size} bytes)`)
console.log(`TORCHSCRIPT_EXPORT=${ptPath}`)

// Generator: generate and save one candidate, so comparison has at least two architectures.
await desk.goto(`${STUDIO}/generator`); await desk.waitForLoadState("networkidle")
await desk.getByRole("button", { name: "Generate candidates" }).click()
const generated = await until(async () => (await desk.getByRole("button", { name: "save to registry" }).count()) > 0, 30000, 500)
if (generated) await desk.getByRole("button", { name: "save to registry" }).first().click()
check("generator: candidates generated and one saved to the registry", generated)

// Model comparison: compare two architectures; policy table present.
await desk.goto(`${STUDIO}/compare`); await desk.waitForLoadState("networkidle")
const boxes = desk.locator('fieldset input[type="checkbox"]')
await boxes.nth(0).check(); await boxes.nth(1).check()
await desk.getByRole("button", { name: /^Compare 2 selected/ }).click()
const compared = await until(async () => (await desk.getByText("(fewest)").count()) > 0, 15000, 500)
const policyRows = await desk.locator("table").first().locator("tbody tr").count()
check("model comparison: 2 architectures compared; policy table lists 7 policies + 4 ablations", compared && policyRows === 11, `policyRows=${policyRows}`)
await desk.screenshot({ path: `${SCREENS}/flow-compare.png`, fullPage: true })

// Model registry: inspect a checkpoint.
await desk.goto(`${STUDIO}/models`); await desk.waitForLoadState("networkidle")
const inspectButtons = desk.getByRole("button", { name: "Inspect" })
if (await inspectButtons.count()) {
  await inspectButtons.last().click()
  const inspected = await until(async () => (await desk.getByText(/tensors · .* parameters/).count()) > 0, 30000, 500)
  check("model registry: checkpoint inspection lists tensors", inspected, await desk.getByText(/tensors · .* parameters/).first().innerText().catch(() => ""))
  await desk.screenshot({ path: `${SCREENS}/flow-model-inspect.png`, fullPage: true })
} else check("model registry: checkpoint inspection lists tensors", false, "no registered checkpoints")

// Training laboratory: queue the default synthetic candidate job and read its measured loss table.
await desk.goto(`${STUDIO}/training`); await desk.waitForLoadState("networkidle")
await desk.getByRole("button", { name: "Queue job" }).click()
const trained = await until(async () => (await desk.getByText(/^training · succeeded/).count()) > 0, 180000)
check("training lab: synthetic candidate job succeeds and shows its loss table", trained && (await desk.getByText(/\(measured\)/).count()) > 0)
await desk.screenshot({ path: `${SCREENS}/flow-training.png`, fullPage: true })

// Results + admin.
await desk.goto(`${STUDIO}/results`); await desk.waitForLoadState("networkidle")
await desk.getByRole("button", { name: "archai_v1_smoke" }).click()
check("research results: smoke result set shows its predictor report", await until(async () => (await desk.getByText("Predictor report (smoke-scale)").count()) > 0, 10000, 500))
await desk.goto(`${STUDIO}/admin`); await desk.waitForLoadState("networkidle")
check("system administration: readiness ready and a live worker listed", (await desk.getByRole("cell", { name: "ready", exact: true }).count()) > 0 && (await desk.locator("li code").count()) > 0)

// ---- mobile: layout + menu on every page (close desktop first so its polls do not share the rate-limit budget) ----
await desk.context().close()
const mobile = await newPage({ width: 390, height: 844 })
for (const [href, title] of PAGES) {
  await mobile.goto(`${STUDIO}${href}`); await mobile.waitForLoadState("networkidle")
  const navHidden = !(await mobile.locator("#primary-nav").isVisible())
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  await mobile.screenshot({ path: `${SCREENS}/mobile${href === "/" ? "-dashboard" : href.replace("/", "-")}.png`, fullPage: true })
  await mobile.getByRole("button", { name: "Menu" }).click()
  const navShown = await mobile.locator("#primary-nav").isVisible()
  const expanded = await mobile.getByRole("button", { name: "Close" }).getAttribute("aria-expanded")
  check(`mobile ${href}: no horizontal overflow; menu toggles nav`, overflow <= 1 && navHidden && navShown && expanded === "true", `overflow=${overflow}px`)
  if (href === "/pareto") await mobile.screenshot({ path: `${SCREENS}/mobile-menu-open.png` })
}

await browser.close()
check("no browser console errors", consoleErrors.length === 0, consoleErrors.slice(0, 5).join(" | "))
const failed = results.filter((item) => !item.ok)
console.log(`SUMMARY ${results.length - failed.length}/${results.length} passed`)
process.exit(failed.length ? 1 : 0)
