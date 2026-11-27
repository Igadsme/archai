"use client"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { downloadFile, downloadJson, request } from "../lib/api"
import { buildGraphModel, diffArchitectures, formatShape, NODE_HEIGHT, NODE_WIDTH, type GraphEdgeModel, type GraphModel, type GraphNodeModel } from "../lib/architectureGraph"
import { defaultCandidateArchitecture } from "../lib/forms"
import type { ArchitectureDetail, ArchitectureItem, Worker } from "../lib/types"
import { architectureDetailResponse, itemsResponse } from "../lib/validators"
import { useQueryParam } from "../studio/hooks"
import { Icon } from "../studio/Icon"
import { formatBytes, formatCompact, formatCount, shortId } from "../studio/ui"

type WorkspaceMode = "explore" | "inspect" | "compare" | "research"
type InspectorTab = "OPERATOR" | "GRAPH" | "LINEAGE"
type ConsoleTab = "EXPERIMENT LOG" | "DIAGNOSTICS" | "TENSOR WATCH" | "SPEC EDITOR" | "WORKERS"
type Selection = { type: "node"; index: number } | { type: "edge"; index: number } | null
type Validation = { status: "pending" | "pass" | "fail" | "offline"; detail?: ArchitectureDetail; error?: string; at?: string }
type Doc = { id: string; draft: boolean; status: "loading" | "ready" | "error"; detail?: ArchitectureDetail; error?: string; validation?: Validation }
type LogEntry = { at: string; level: "INFO" | "PASS" | "WARN" | "FAIL" | "SELECT"; message: string; code?: string }

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const ZOOM = { min: 0.4, max: 2.5, step: 0.1 }
const TAB_LIMIT = 6
const now = () => new Date().toISOString().slice(11, 23)
const DRAFT_PREFIX = "draft:"

function stored<T>(key: string, fallback: T, parse: (raw: string) => T | null): T {
  try { const raw = localStorage.getItem(key); const value = raw === null ? null : parse(raw); return value ?? fallback } catch { return fallback }
}
const storedNumber = (key: string, fallback: number) => stored(key, fallback, (raw) => { const value = Number(raw); return Number.isFinite(value) && value > 0 ? value : null })

export function Explorer() {
  const requestedId = useQueryParam("id")
  const registry = usePoll<{ items: ArchitectureItem[] }>("/v1/architectures?limit=200", 15_000, itemsResponse)
  const workers = usePoll<{ configured: boolean; status: string; workers: Worker[] }>("/v1/infrastructure/workers", 15_000)
  const [docs, setDocs] = useState<Record<string, Doc>>({})
  const [tabs, setTabs] = useState<string[]>(() => stored("archai.explorer.tabs", [] as string[], (raw) => { const value = JSON.parse(raw) as unknown; return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && !item.startsWith(DRAFT_PREFIX)) : null }))
  const [activeId, setActiveId] = useState<string | null>(() => stored("archai.explorer.active", null as string | null, (raw) => raw.startsWith(DRAFT_PREFIX) ? null : raw))
  const [compareBase, setCompareBase] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [selection, setSelection] = useState<Selection>(null)
  const [selectedNodes, setSelectedNodes] = useState<number[]>([])
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("OPERATOR")
  const [consoleTab, setConsoleTab] = useState<ConsoleTab>("EXPERIMENT LOG")
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [leftWidth, setLeftWidth] = useState(() => storedNumber("archai.explorer.left", 206))
  const [rightWidth, setRightWidth] = useState(() => storedNumber("archai.explorer.right", 292))
  const [consoleHeight, setConsoleHeight] = useState(() => storedNumber("archai.explorer.console", 168))
  const [mode, setMode] = useState<WorkspaceMode>(() => stored("archai.explorer.mode", "explore" as WorkspaceMode, (raw) => (["explore", "inspect", "compare", "research"] as string[]).includes(raw) ? raw as WorkspaceMode : null))
  const [leftCollapsed, setLeftCollapsed] = useState(() => stored("archai.explorer.leftCollapsed", false, (raw) => raw === "true"))
  const [rightCollapsed, setRightCollapsed] = useState(() => stored("archai.explorer.rightCollapsed", false, (raw) => raw === "true"))
  const [browserFilter, setBrowserFilter] = useState<"ALL" | "OPEN" | "SMALLEST">("ALL")
  const [nodeQuery, setNodeQuery] = useState("")
  const [tensorLabels, setTensorLabels] = useState(true)
  const [layoutLocked, setLayoutLocked] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([])
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; index: number } | null>(null)
  const [validationExpanded, setValidationExpanded] = useState(false)
  const [log, setLog] = useState<LogEntry[]>([])
  const [draftText, setDraftText] = useState(() => JSON.stringify(defaultCandidateArchitecture, null, 2))
  const [specBusy, setSpecBusy] = useState(false)
  const [specMessage, setSpecMessage] = useState<{ tone: "pass" | "fail"; text: string } | null>(null)
  const dragging = useRef<{ mode: "left" | "right" | "console" | "pan"; startX: number; startY: number; startValue: number; startPan: { x: number; y: number }; scale: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const sizes = useRef({ leftWidth, rightWidth, consoleHeight })
  sizes.current = { leftWidth, rightWidth, consoleHeight }

  const addLog = useCallback((level: LogEntry["level"], message: string, code?: string) => setLog((current) => [{ at: now(), level, message, code }, ...current].slice(0, 80)), [])

  const runValidation = useCallback(async (id: string, detail: ArchitectureDetail) => {
    setDocs((current) => ({ ...current, [id]: { ...current[id], validation: { status: "pending" } } }))
    const outcome = await request<ArchitectureDetail>("/v1/architectures/validate", { method: "POST", body: detail.architecture, validate: architectureDetailResponse })
    const validation: Validation = outcome.ok ? { status: "pass", detail: outcome.data, at: now() }
      : { status: outcome.error.kind === "http" || outcome.error.kind === "invalid_response" ? "fail" : "offline", error: outcome.error.message, at: now() }
    setDocs((current) => ({ ...current, [id]: { ...current[id], validation } }))
    addLog(outcome.ok ? "PASS" : "FAIL", outcome.ok ? `Validation passed for ${shortId(id.replace(DRAFT_PREFIX, ""))}` : `Validation failed: ${outcome.error.message}`, "POST /validate")
  }, [addLog])

  const loadDoc = useCallback(async (id: string) => {
    setDocs((current) => current[id]?.status === "ready" ? current : { ...current, [id]: { id, draft: false, status: "loading" } })
    const outcome = await request<ArchitectureDetail>(`/v1/architectures/${encodeURIComponent(id)}`, { validate: architectureDetailResponse })
    if (!outcome.ok) {
      setDocs((current) => ({ ...current, [id]: { id, draft: false, status: "error", error: outcome.error.message } }))
      addLog("FAIL", `Could not load ${shortId(id)}: ${outcome.error.message}`, `GET /architectures`)
      return
    }
    setDocs((current) => ({ ...current, [id]: { id, draft: false, status: "ready", detail: outcome.data } }))
    addLog("INFO", `Loaded architecture specification ${shortId(id)} · ${outcome.data.architecture.nodes.length} nodes · ${outcome.data.architecture.edges.length} edges`, "GET /architectures")
    void runValidation(id, outcome.data)
  }, [addLog, runValidation])

  const openDoc = useCallback((id: string) => {
    setActiveId(id)
    setTabs((current) => current.includes(id) ? current : [...current, id].slice(-TAB_LIMIT))
    setSelection(null); setSelectedNodes([])
  }, [])

  useEffect(() => { if (requestedId) openDoc(requestedId) }, [openDoc, requestedId])
  useEffect(() => {
    if (activeId || requestedId || !registry.data) return
    const first = registry.data.items[0]
    if (first) openDoc(first.architecture_id)
  }, [activeId, openDoc, registry.data, requestedId])
  useEffect(() => {
    for (const id of tabs) if (!id.startsWith(DRAFT_PREFIX) && !docs[id]) void loadDoc(id)
  }, [docs, loadDoc, tabs])
  useEffect(() => {
    localStorage.setItem("archai.explorer.tabs", JSON.stringify(tabs.filter((tab) => !tab.startsWith(DRAFT_PREFIX))))
    if (activeId && !activeId.startsWith(DRAFT_PREFIX)) localStorage.setItem("archai.explorer.active", activeId)
  }, [activeId, tabs])
  useEffect(() => {
    localStorage.setItem("archai.explorer.mode", mode)
    localStorage.setItem("archai.explorer.leftCollapsed", String(leftCollapsed))
    localStorage.setItem("archai.explorer.rightCollapsed", String(rightCollapsed))
  }, [leftCollapsed, mode, rightCollapsed])

  const doc = activeId ? docs[activeId] : undefined
  const detail = doc?.detail
  const graph = useMemo<{ model: GraphModel | null; error: string | null }>(() => {
    if (!detail) return { model: null, error: null }
    try { return { model: buildGraphModel(detail.architecture), error: null } } catch (error) { return { model: null, error: error instanceof Error ? error.message : "graph could not be laid out" } }
  }, [detail])
  const model = graph.model
  useEffect(() => { setZoom(1); setPan({ x: 0, y: 0 }); setCollapsedGroups([]) }, [activeId])

  const registryItems = items(registry.data)
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const list = registryItems.filter((item) => !needle || `${item.architecture_id} ${item.search_space}`.toLowerCase().includes(needle))
      .filter((item) => browserFilter !== "OPEN" || tabs.includes(item.architecture_id))
    return browserFilter === "SMALLEST" ? [...list].sort((a, b) => a.metrics.parameters - b.metrics.parameters) : list
  }, [browserFilter, query, registryItems, tabs])
  const paramRange = useMemo(() => registryItems.length ? [Math.min(...registryItems.map((item) => item.metrics.parameters)), Math.max(...registryItems.map((item) => item.metrics.parameters))] : null, [registryItems])

  const selectedNode = model && selection?.type === "node" ? model.nodes[selection.index] ?? null : null
  const selectedEdge = model && selection?.type === "edge" ? model.edges[selection.index] ?? null : null
  const visibleNode = useCallback((index: number) => !!model && !collapsedGroups.includes(model.nodes[index].group), [collapsedGroups, model])

  const closeTab = (id: string) => {
    const next = tabs.filter((tab) => tab !== id)
    setTabs(next)
    if (activeId === id) { setActiveId(next[next.length - 1] ?? null); setSelection(null); setSelectedNodes([]) }
    if (compareBase === id) setCompareBase(null)
  }

  const fitGraph = useCallback(() => { setZoom(1); setPan({ x: 0, y: 0 }) }, [])
  const fitSelection = useCallback((indices: number[] = selectedNodes) => {
    if (!model || !indices.length) return
    const nodes = indices.map((index) => model.nodes[index]).filter(Boolean)
    const minX = Math.min(...nodes.map((node) => node.x)); const maxX = Math.max(...nodes.map((node) => node.x + NODE_WIDTH))
    const minY = Math.min(...nodes.map((node) => node.y)); const maxY = Math.max(...nodes.map((node) => node.y + NODE_HEIGHT))
    const next = clamp(Math.min(model.width / (maxX - minX + 160), model.height / (maxY - minY + 140)), ZOOM.min, ZOOM.max)
    setZoom(next)
    setPan({ x: model.width / 2 - ((minX + maxX) / 2) * next, y: model.height / 2 - ((minY + maxY) / 2) * next })
  }, [model, selectedNodes])
  const focusNode = useCallback((index: number) => {
    setSelection({ type: "node", index }); setSelectedNodes([index]); setInspectorTab("OPERATOR"); fitSelection([index])
  }, [fitSelection])

  const selectNode = (event: React.MouseEvent | React.KeyboardEvent, index: number) => {
    if ("key" in event && event.key !== "Enter" && event.key !== " ") return
    event.preventDefault(); event.stopPropagation()
    setSelection({ type: "node", index }); setInspectorTab("OPERATOR")
    if (event.shiftKey) setSelectedNodes((current) => current.includes(index) ? current.filter((item) => item !== index) : [...current, index])
    else setSelectedNodes([index])
    if (model) addLog("SELECT", `Inspector focused on N${String(index).padStart(2, "0")} / ${model.nodes[index].id} (${model.nodes[index].op})`, "local event")
  }
  const selectEdge = (event: React.MouseEvent | React.KeyboardEvent, index: number) => {
    if ("key" in event && event.key !== "Enter" && event.key !== " ") return
    event.preventDefault(); event.stopPropagation()
    setSelection({ type: "edge", index }); setSelectedNodes([]); setInspectorTab("OPERATOR")
    if (model) addLog("SELECT", `Inspector focused on edge ${model.edges[index].id}`, "local event")
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.matches("input,select,textarea") || event.metaKey || event.ctrlKey || event.altKey) return
      if (event.key === "+" || event.key === "=") setZoom((value) => clamp(value + ZOOM.step, ZOOM.min, ZOOM.max))
      else if (event.key === "-") setZoom((value) => clamp(value - ZOOM.step, ZOOM.min, ZOOM.max))
      else if (event.key.toLowerCase() === "f") fitGraph()
      else if (event.key === "Enter" && selectedNodes.length && !target?.closest(".graph-node-advanced,.advanced-edge")) fitSelection()
      else if (event.key.toLowerCase() === "l") setInspectorTab("LINEAGE")
      else if (event.key.toLowerCase() === "g") setInspectorTab("GRAPH")
      else if (event.key.toLowerCase() === "o") setInspectorTab("OPERATOR")
      else if (event.key === "/") { event.preventDefault(); searchRef.current?.focus() }
      else if (event.key === "Escape") { setContextMenu(null); setSelectedNodes([]); setValidationExpanded(false) }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [fitGraph, fitSelection, selectedNodes.length])

  useEffect(() => {
    const move = (event: PointerEvent) => {
      const state = dragging.current
      if (!state) return
      if (state.mode === "left") setLeftWidth(clamp(state.startValue + event.clientX - state.startX, 160, 360))
      if (state.mode === "right") setRightWidth(clamp(state.startValue - event.clientX + state.startX, 250, 460))
      if (state.mode === "console") setConsoleHeight(clamp(state.startValue - event.clientY + state.startY, 110, 360))
      if (state.mode === "pan") setPan({ x: state.startPan.x + (event.clientX - state.startX) * state.scale, y: state.startPan.y + (event.clientY - state.startY) * state.scale })
    }
    const up = () => {
      const state = dragging.current
      if (state?.mode === "left") localStorage.setItem("archai.explorer.left", String(sizes.current.leftWidth))
      if (state?.mode === "right") localStorage.setItem("archai.explorer.right", String(sizes.current.rightWidth))
      if (state?.mode === "console") localStorage.setItem("archai.explorer.console", String(sizes.current.consoleHeight))
      dragging.current = null
      document.body.classList.remove("is-resizing")
    }
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", up)
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up) }
  }, [])

  const svgScale = () => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect || !model || !rect.width || !rect.height) return 1
    return Math.max(model.width / rect.width, model.height / rect.height)
  }
  const beginResize = (which: "left" | "right" | "console", event: React.PointerEvent) => {
    dragging.current = { mode: which, startX: event.clientX, startY: event.clientY, startValue: which === "left" ? leftWidth : which === "right" ? rightWidth : consoleHeight, startPan: pan, scale: 1 }
    document.body.classList.add("is-resizing")
  }
  const resizeWithKeys = (which: "left" | "right" | "console", event: React.KeyboardEvent) => {
    const delta = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -16 : event.key === "ArrowRight" || event.key === "ArrowDown" ? 16 : 0
    if (!delta) return
    event.preventDefault()
    if (which === "left") setLeftWidth((value) => clamp(value + delta, 160, 360))
    if (which === "right") setRightWidth((value) => clamp(value - delta, 250, 460))
    if (which === "console") setConsoleHeight((value) => clamp(value - delta, 110, 360))
  }
  const beginPan = (event: React.PointerEvent) => {
    if (layoutLocked || event.button !== 0) return
    if ((event.target as Element).closest(".graph-node-advanced,.edge-hit,.canvas-overlays button,.graph-minimap,.validation-popover,.graph-compare-strip")) return
    setContextMenu(null)
    dragging.current = { mode: "pan", startX: event.clientX, startY: event.clientY, startValue: 0, startPan: pan, scale: svgScale() }
  }
  const onWheel = (event: React.WheelEvent) => {
    if (!event.ctrlKey && !event.metaKey) return
    setZoom((value) => clamp(value * (event.deltaY < 0 ? 1.1 : 0.9), ZOOM.min, ZOOM.max))
  }

  const effectiveLeft = leftCollapsed || mode === "inspect" ? 0 : mode === "compare" ? 190 : leftWidth
  const effectiveRight = rightCollapsed || mode === "research" ? 0 : mode === "inspect" ? 400 : mode === "compare" ? 350 : rightWidth
  const effectiveConsole = mode === "research" ? Math.max(260, consoleHeight) : mode === "compare" ? 120 : consoleHeight

  const validation = doc?.validation
  const apiTotals = detail?.analytical_metrics
  const totalsMatch = !!model && !!apiTotals && model.totals.parameters === apiTotals.parameters && model.totals.flops === apiTotals.flops && model.totals.activationMemoryBytes === apiTotals.activation_memory_bytes
  const hashMatches = !!validation?.detail && !!activeId && (doc?.draft ? true : validation.detail.hash === activeId)
  const diagnostics = buildDiagnostics(doc, model, totalsMatch, hashMatches, graph.error)
  const otherTabs = tabs.filter((tab) => tab !== activeId && docs[tab]?.detail)
  const baseId = compareBase && otherTabs.includes(compareBase) ? compareBase : otherTabs[0] ?? null
  const baseDoc = baseId ? docs[baseId] : undefined

  const exportGraph = () => {
    if (!detail || !model || !activeId) return
    downloadJson(`${shortId(activeId.replace(DRAFT_PREFIX, ""), 16)}-graph.json`, {
      exported_at: new Date().toISOString(), architecture_id: doc?.draft ? null : activeId, canonical_hash: detail.hash, registered: !doc?.draft,
      evidence: { analytical_metrics: "computed from the graph (archai_compiler.metrics); not trained or measured", latency: "not measured", trained_weights: "none attached" },
      analytical_metrics: detail.analytical_metrics, validation: validation ? { status: validation.status, at_utc: validation.at, error: validation.error ?? null, hash: validation.detail?.hash ?? null } : null,
      architecture: detail.architecture,
      graph: { layers: model.layers, groups: model.groups, nodes: model.nodes.map(({ module, ...node }) => ({ ...node, pytorch: module })), edges: model.edges },
    })
    addLog("INFO", `Exported graph JSON for ${shortId(activeId.replace(DRAFT_PREFIX, ""))}`, "local export")
  }
  const exportFromApi = async (format: "json" | "pytorch") => {
    if (!activeId || doc?.draft) return
    addLog("INFO", `Requested ${format === "json" ? "canonical JSON" : "TorchScript"} export`, `GET /export?format=${format}`)
    const error = await downloadFile(`/v1/architectures/${encodeURIComponent(activeId)}/export?format=${format}`, `${shortId(activeId, 16)}.${format === "json" ? "json" : "pt"}`)
    if (error) addLog("FAIL", `Export failed: ${error}`, "GET /export")
    else addLog("PASS", format === "pytorch" ? "Downloaded TorchScript module (load with torch.jit.load)" : "Downloaded canonical JSON", "GET /export")
  }
  const submitSpec = async (register: boolean) => {
    let body: unknown
    try { body = JSON.parse(draftText) } catch (error) { setSpecMessage({ tone: "fail", text: `Spec is not valid JSON: ${error instanceof Error ? error.message : "parse error"}` }); return }
    setSpecBusy(true); setSpecMessage(null)
    const outcome = await request<ArchitectureDetail>(register ? "/v1/architectures" : "/v1/architectures/validate", { method: "POST", body, validate: architectureDetailResponse })
    setSpecBusy(false)
    if (!outcome.ok) {
      setSpecMessage({ tone: "fail", text: outcome.error.message })
      addLog("FAIL", `${register ? "Registration" : "Validation"} rejected: ${outcome.error.message}`, register ? "POST /architectures" : "POST /validate")
      return
    }
    const id = register ? outcome.data.hash : `${DRAFT_PREFIX}${outcome.data.hash}`
    setDocs((current) => ({ ...current, [id]: { id, draft: !register, status: "ready", detail: outcome.data, validation: { status: "pass", detail: outcome.data, at: now() } } }))
    openDoc(id)
    setSpecMessage({ tone: "pass", text: register ? `Registered ${shortId(outcome.data.hash)} (canonical hash).` : `Valid — canonical hash ${shortId(outcome.data.hash)}. Opened as an unregistered draft.` })
    addLog("PASS", `${register ? "Registered" : "Validated"} spec ${shortId(outcome.data.hash)}`, register ? "POST /architectures" : "POST /validate")
    if (register) registry.refresh()
  }

  const title = activeId ? shortId(activeId.replace(DRAFT_PREFIX, ""), 16) : "No architecture"
  const viewBox = model ? `0 0 ${model.width} ${model.height}` : "0 0 1080 430"
  const semantic = zoom < 0.75 ? "semantic-coarse" : zoom > 1.4 ? "semantic-detailed" : "semantic-standard"
  const collapsible = model?.groups.filter((group) => group !== "INPUT" && group !== "OUTPUT") ?? []
  const visibleCount = model ? model.nodes.filter((node) => !collapsedGroups.includes(node.group)).length : 0

  return <div className="explorer-pro" style={{ "--left-pane": `${effectiveLeft}px`, "--right-pane": `${effectiveRight}px`, "--console-pane": `${effectiveConsole}px` } as React.CSSProperties}>
    <div className="workbench-header">
      <div className="workbench-title"><span className="eyebrow">NEURAL ARCHITECTURE / ENGINEERING WORKSPACE</span>
        <h1>{title}<small>{detail?.architecture.search_space ?? (doc?.status === "loading" ? "loading…" : "—")}</small><span>{doc?.draft ? "unregistered draft" : detail ? `schema ${detail.architecture.schema_version ?? "1.0"}` : ""}</span></h1></div>
      <div className="workbench-kpis">
        <span><small>PARAMETERS · ANALYTICAL</small><b>{formatCompact(apiTotals?.parameters)}</b></span>
        <span><small>FLOPs · ANALYTICAL</small><b>{formatCompact(apiTotals?.flops)}</b></span>
        <span><small>ACTIVATIONS · ANALYTICAL</small><b>{formatBytes(apiTotals?.activation_memory_bytes)}</b></span>
        <span><small>NODES / EDGES</small><b>{detail ? `${detail.architecture.nodes.length} / ${detail.architecture.edges.length}` : "—"}</b></span>
        <span><small>LATENCY</small><b className="not-measured">NOT MEASURED</b></span>
      </div>
      <div className="workbench-actions">
        <div className="mode-switch" role="group" aria-label="Workspace mode">{(["explore", "inspect", "compare", "research"] as WorkspaceMode[]).map((item) => <button key={item} aria-pressed={mode === item} className={mode === item ? "active" : ""} onClick={() => setMode(item)} title={`${item} mode`}>{item.toUpperCase()}</button>)}</div>
        <button className="button" onClick={exportGraph} disabled={!model}><Icon name="download" /> Export graph</button>
      </div>
    </div>

    <div className="document-tabs" role="tablist" aria-label="Open architectures">
      {tabs.map((id) => <div key={id} role="tab" aria-selected={id === activeId} tabIndex={0} className={`doc-tab ${id === activeId ? "active" : ""}`} onClick={() => { setActiveId(id); setSelection(null); setSelectedNodes([]) }} onKeyDown={(event) => event.key === "Enter" && setActiveId(id)}>
        <i className={docs[id]?.draft || id.startsWith(DRAFT_PREFIX) ? "draft" : docs[id]?.validation?.status === "fail" ? "fail" : ""} />{shortId(id.replace(DRAFT_PREFIX, ""), 10)}{id.startsWith(DRAFT_PREFIX) ? " · draft" : ""}
        <button aria-label={`Close ${shortId(id.replace(DRAFT_PREFIX, ""), 10)}`} onClick={(event) => { event.stopPropagation(); closeTab(id) }}>×</button></div>)}
      <button className="new-tab" title="Open next registered architecture" aria-label="Open next registered architecture" onClick={() => { const next = registryItems.find((item) => !tabs.includes(item.architecture_id)); if (next) openDoc(next.architecture_id); else setConsoleTab("SPEC EDITOR") }}>+</button>
      <div className="tab-spacer" />
      <span className="shortcut-hint"><kbd>F</kbd> FIT <kbd>+</kbd><kbd>−</kbd> ZOOM <kbd>G</kbd> GRAPH <kbd>L</kbd> LINEAGE <kbd>/</kbd> SEARCH</span>
    </div>

    <div className="pro-grid">
      {effectiveLeft > 0 && <aside className="architecture-browser" aria-label="Architecture index">
        <div className="pane-title"><span>ARCHITECTURE INDEX</span><span>{filtered.length} / {registryItems.length}</span><button title="Collapse architecture browser" aria-label="Collapse architecture browser" onClick={() => setLeftCollapsed(true)}>‹</button></div>
        <label className="architecture-search"><span aria-hidden="true">⌕</span><input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Hash, search space…" aria-label="Search architectures" /><kbd>/</kbd></label>
        <div className="browser-filters">{(["ALL", "OPEN", "SMALLEST"] as const).map((filter) => <button key={filter} aria-pressed={browserFilter === filter} className={browserFilter === filter ? "active" : ""} onClick={() => setBrowserFilter(filter)}>{filter}</button>)}</div>
        <div className="architecture-tree">
          <div className="tree-heading">REGISTRY / HASH-ADDRESSED <span>{registryItems.length}</span></div>
          {!registry.loaded ? <div className="tree-note">Loading registry…</div> : registry.error ? <div className="tree-note error">Registry unavailable: {registry.error}</div>
            : filtered.length === 0 ? <div className="tree-note">{registryItems.length ? "No architecture matches." : "No architectures registered. Use SPEC EDITOR below to validate and register one."}</div>
            : filtered.map((item) => <button key={item.architecture_id} className={item.architecture_id === activeId ? "active" : ""} onClick={() => openDoc(item.architecture_id)} aria-label={`Open architecture ${shortId(item.architecture_id)}`}>
              <i className={tabs.includes(item.architecture_id) ? "" : "closed"} /><span><b>{shortId(item.architecture_id)}</b><small>{item.search_space}</small></span>
              <span><code>{formatCompact(item.metrics.parameters)}</code><small>{formatCompact(item.metrics.flops)} FLOPs</small></span></button>)}
          {tabs.some((tab) => tab.startsWith(DRAFT_PREFIX)) && <div className="tree-heading collapsed">UNREGISTERED DRAFTS <span>{tabs.filter((tab) => tab.startsWith(DRAFT_PREFIX)).length}</span></div>}
        </div>
        <div className="browser-budget"><div><span>PARAMETER RANGE · ANALYTICAL</span><b>{paramRange ? `${formatCompact(paramRange[0])} – ${formatCompact(paramRange[1])}` : "—"}</b></div>
          <i><span style={{ width: `${paramRange && apiTotals ? clamp(((apiTotals.parameters - paramRange[0]) / (paramRange[1] - paramRange[0] || 1)) * 100, 2, 100) : 0}%` }} /></i>
          <small>Position of the open architecture in the registry range</small></div>
      </aside>}
      {effectiveLeft > 0 && <div className="vertical-resizer left-resizer" role="separator" aria-orientation="vertical" aria-label="Resize architecture browser" tabIndex={0} onPointerDown={(event) => beginResize("left", event)} onKeyDown={(event) => resizeWithKeys("left", event)} />}

      <main className="advanced-graph" aria-label="Computation graph">
        <div className="graph-commandbar">
          <div className="graph-breadcrumb"><Icon name="layers" /><span>MODEL</span><b>/</b><span>{detail?.architecture.search_space?.toUpperCase() ?? "—"}</span><b>/</b><strong>DAG VIEW</strong></div>
          <label className="node-search"><Icon name="search" /><input value={nodeQuery} onChange={(event) => setNodeQuery(event.target.value)} onKeyDown={(event) => {
            if (event.key !== "Enter" || !model) return
            const needle = nodeQuery.trim().toLowerCase()
            const index = model.nodes.findIndex((node) => `${node.id} ${node.op} ${node.group}`.toLowerCase().includes(needle))
            if (index >= 0) focusNode(index); else addLog("WARN", `No node matches "${nodeQuery}"`, "node search")
          }} placeholder="Focus node…" aria-label="Search graph nodes" /><kbd>↵</kbd></label>
          {!effectiveLeft && <button className="restore-pane left" onClick={() => { setLeftCollapsed(false); if (mode === "inspect") setMode("explore") }} title="Show architecture browser" aria-label="Show architecture browser">›</button>}
          <div className="graph-tools">
            <button onClick={() => setZoom((value) => clamp(value - ZOOM.step, ZOOM.min, ZOOM.max))} title="Zoom out" aria-label="Zoom out"><Icon name="zoomOut" /></button><code aria-live="polite">{Math.round(zoom * 100)}%</code>
            <button onClick={() => setZoom((value) => clamp(value + ZOOM.step, ZOOM.min, ZOOM.max))} title="Zoom in" aria-label="Zoom in"><Icon name="zoomIn" /></button>
            <button onClick={fitGraph} title="Fit graph" aria-label="Fit graph"><Icon name="fit" /></button>
            <button onClick={() => fitSelection()} title="Fit selection" aria-label="Fit selection" disabled={!selectedNodes.length}><Icon name="compare" /></button><span />
            <button className={tensorLabels ? "active" : ""} aria-pressed={tensorLabels} onClick={() => setTensorLabels((value) => !value)} title="Toggle tensor labels" aria-label="Toggle tensor labels"><Icon name="eye" /></button>
            <button className={layoutLocked ? "active" : ""} aria-pressed={layoutLocked} onClick={() => setLayoutLocked((value) => !value)} title="Lock canvas panning" aria-label="Lock canvas panning"><Icon name="lock" /></button>
          </div>
        </div>
        <div className={`advanced-canvas ${layoutLocked ? "locked" : ""}`} onPointerDown={beginPan} onWheel={onWheel}>
          <div className="canvas-grid fine" style={{ backgroundPosition: `${pan.x}px ${pan.y}px`, backgroundSize: `${16 * zoom}px ${16 * zoom}px` }} />
          {!model ? <div className="canvas-empty">{doc?.status === "loading" ? <><i className="spinner" /><b>Loading architecture…</b></>
            : doc?.status === "error" ? <><Icon name="alert" /><b>Could not load {shortId(activeId)}</b><span>{doc.error}</span><button className="button" onClick={() => activeId && void loadDoc(activeId)}>Retry</button></>
            : graph.error ? <><Icon name="alert" /><b>Graph could not be laid out</b><span>{graph.error}</span></>
            : <><Icon name="explorer" size={30} /><b>No architecture open</b><span>{registry.error ? `Registry unavailable: ${registry.error}` : "Open a registered architecture from the index, or validate a spec in the SPEC EDITOR console tab."}</span>
              <button className="button" onClick={() => { setConsoleTab("SPEC EDITOR"); if (mode === "compare") setMode("explore") }}>Open spec editor</button></>}</div>
          : <svg ref={svgRef} viewBox={viewBox} className={`advanced-network ${semantic}`} role="group" aria-label={`Computation graph of ${title}: ${model.nodes.length} nodes, ${model.edges.length} edges`}>
            <defs>
              <marker id="pro-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="#657b89" /></marker>
              <marker id="pro-residual" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="#c49a57" /></marker>
            </defs>
            <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              <g className="stage-regions">{Array.from({ length: model.layers }, (_, layer) => <g key={layer}><rect x={40 + layer * 145 - 8} y={22} width={116} height={model.height - 44} /><text x={40 + layer * 145 - 2} y={36}>LAYER {layer}</text></g>)}</g>
              <g className="edge-layer">{model.edges.map((edge, index) => visibleNode(edge.from) && visibleNode(edge.to) ? <g key={edge.id} className={`advanced-edge ${edge.kind} ${selectedEdge?.id === edge.id ? "selected" : ""}`} onClick={(event) => selectEdge(event, index)}>
                <path d={edge.path} markerEnd={edge.kind === "residual" ? "url(#pro-residual)" : "url(#pro-arrow)"} />
                <path className="edge-hit" d={edge.path} role="button" tabIndex={0} aria-label={`Edge ${edge.source} to ${edge.target}, ${edge.kind}, tensor ${formatShape(edge.shape)}`} onKeyDown={(event) => selectEdge(event, index)} />
                {tensorLabels && <text><textPath href={`#label-${index}`} startOffset="50%">{edge.shape[0]}×{edge.shape[1]}×{edge.shape[2]}</textPath></text>}
                <path className="edge-label-path" id={`label-${index}`} d={edge.path} />
              </g> : null)}</g>
              <g className="node-layer">{model.nodes.map((node) => visibleNode(node.index) ? <g key={node.id}
                className={`graph-node-advanced operator-${node.op} ${selectedNodes.includes(node.index) ? "selected" : ""} ${selection?.type === "node" && selection.index === node.index ? "primary" : ""}`}
                transform={`translate(${node.x} ${node.y})`} onClick={(event) => selectNode(event, node.index)} onKeyDown={(event) => selectNode(event, node.index)}
                onContextMenu={(event) => { event.preventDefault(); event.stopPropagation(); setContextMenu({ x: event.clientX, y: event.clientY, index: node.index }) }}
                role="button" aria-pressed={selectedNodes.includes(node.index)} aria-label={`${node.id}, ${node.op}, output ${formatShape(node.outputShape)}`} tabIndex={0} data-node-id={node.id}>
                <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx="2" /><rect className="node-accent" width="3" height={NODE_HEIGHT} />
                <text x="10" y="14" className="node-eyebrow">N{String(node.index).padStart(2, "0")} · {node.op.toUpperCase()}</text>
                <text x="10" y="35" className="node-title">{node.id.length > 13 ? `${node.id.slice(0, 12)}…` : node.id}</text>
                <text x="10" y="51" className="node-tensor">{node.outputShape[0]}×{node.outputShape[1]}×{node.outputShape[2]}</text>
                <line x1="10" y1="59" x2="90" y2="59" />
                <text x="10" y="72" className="node-cost">{formatCompact(node.parameters)} params</text><text x="89" y="72" textAnchor="end" className="node-cost">{formatCompact(node.flops)}</text>
                <circle cx="0" cy="40" r="3" /><circle cx="100" cy="40" r="3" />
              </g> : null)}</g>
            </g>
          </svg>}
          {model && <div className="canvas-overlays">
            {collapsible.length > 0 && <div className="stage-controls"><span>STAGES</span>{collapsible.map((group) => <button key={group} aria-pressed={collapsedGroups.includes(group)} className={collapsedGroups.includes(group) ? "collapsed" : ""} onClick={() => setCollapsedGroups((current) => current.includes(group) ? current.filter((item) => item !== group) : [...current, group])}>{collapsedGroups.includes(group) ? "+" : "−"} {group}</button>)}<button onClick={() => { setCollapsedGroups([]); fitGraph() }}>AUTO LAYOUT</button></div>}
            <button className={`validation-pill ${validationExpanded ? "expanded" : ""} ${validation?.status ?? "pending"}`} aria-expanded={validationExpanded} onClick={() => setValidationExpanded((value) => !value)}>
              <Icon name={validation?.status === "pass" ? "check" : "alert"} />
              <span><b>{validation?.status === "pass" ? "GRAPH VALID" : validation?.status === "fail" ? "GRAPH INVALID" : validation?.status === "offline" ? "VALIDATOR OFFLINE" : "VALIDATING"}</b><small>{diagnostics.filter((item) => item.level === "PASS").length} checks · {diagnostics.filter((item) => item.level === "FAIL").length} errors</small></span><Icon name="chevron" /></button>
            {validationExpanded && <div className="validation-popover" role="dialog" aria-label="Validation results"><header>API VALIDATION <span className={`status status-${validation?.status === "pass" ? "teal" : validation?.status === "fail" ? "red" : "amber"}`}><i />{(validation?.status ?? "pending").toUpperCase()}</span></header>
              {diagnostics.filter((item) => item.level === "PASS" || item.level === "FAIL").map((item) => <div key={item.message}><Icon name={item.level === "PASS" ? "check" : "alert"} /><span>{item.message}</span><b className={item.level === "FAIL" ? "fail" : ""}>{item.level}</b></div>)}
              {validation?.error ? <p className="popover-error">{validation.error}</p> : null}
              <small>POST /v1/architectures/validate{validation?.at ? ` · ${validation.at} UTC` : ""}</small></div>}
            {mode === "compare" && detail && <div className="graph-compare-strip">{baseDoc?.detail ? (() => {
              const base = baseDoc.detail
              const diff = diffArchitectures(base.architecture, detail.architecture)
              const pct = (a: number, b: number) => b === 0 ? "—" : `${a >= b ? "+" : ""}${(((a - b) / b) * 100).toFixed(1)}%`
              return <><header><span>COMPARE / {shortId(activeId?.replace(DRAFT_PREFIX, ""), 8)}</span><b>vs</b>
                <select aria-label="Comparison base" value={baseId ?? ""} onChange={(event) => setCompareBase(event.target.value)}>{otherTabs.map((tab) => <option key={tab} value={tab}>{shortId(tab.replace(DRAFT_PREFIX, ""), 8)}</option>)}</select></header>
                <div><span>PARAMETERS</span><code>{formatCompact(detail.analytical_metrics.parameters)}</code><em>{pct(detail.analytical_metrics.parameters, base.analytical_metrics.parameters)}</em></div>
                <div><span>FLOPs</span><code>{formatCompact(detail.analytical_metrics.flops)}</code><em>{pct(detail.analytical_metrics.flops, base.analytical_metrics.flops)}</em></div>
                <div><span>TOPOLOGY</span><code>{detail.architecture.nodes.length} nodes</code><em>{diff.added.length + diff.removed.length + diff.changed.length} NODE Δ · {diff.edgeDelta} EDGE Δ</em></div></>
            })() : <header><span>COMPARE</span><b>—</b><span>Open a second architecture tab to compare</span></header>}</div>}
            <div className="graph-minimap" role="button" tabIndex={0} aria-label="Minimap: click to move the viewport" onClick={(event) => {
              const rect = event.currentTarget.querySelector("svg")!.getBoundingClientRect()
              const px = ((event.clientX - rect.left) / rect.width) * model.width
              const py = ((event.clientY - rect.top) / rect.height) * model.height
              setPan({ x: model.width / 2 - px * zoom, y: model.height / 2 - py * zoom })
            }} onKeyDown={(event) => event.key === "Enter" && fitGraph()}>
              <svg viewBox={viewBox} preserveAspectRatio="xMidYMid meet">{model.edges.map((edge) => <path key={edge.id} d={edge.path} />)}{model.nodes.map((node) => visibleNode(node.index) ? <rect key={node.id} x={node.x} y={node.y} width={NODE_WIDTH} height={NODE_HEIGHT} /> : null)}
                <rect className="viewport-box" x={-pan.x / zoom} y={-pan.y / zoom} width={model.width / zoom} height={model.height / zoom} /></svg>
              <span>MINIMAP / {visibleCount} OF {model.nodes.length} NODES</span></div>
            <div className="canvas-legend"><span><i /> DATA</span><span><i className="residual" /> RESIDUAL</span><span><i className="branch" /> BRANCH</span>{selectedNodes.length > 1 && <strong>{selectedNodes.length} NODES SELECTED</strong>}<b>{layoutLocked ? "CANVAS LOCKED" : "DRAG CANVAS TO PAN · SHIFT+CLICK MULTI-SELECT · CTRL+WHEEL ZOOM"}</b></div>
          </div>}
        </div>
      </main>

      {effectiveRight > 0 && <div className="vertical-resizer right-resizer" role="separator" aria-orientation="vertical" aria-label="Resize inspector" tabIndex={0} onPointerDown={(event) => beginResize("right", event)} onKeyDown={(event) => resizeWithKeys("right", event)} />}
      {effectiveRight > 0 && <aside className="technical-inspector" aria-label="Technical inspector">
        <div className="inspector-tabs" role="tablist">{(["OPERATOR", "GRAPH", "LINEAGE"] as InspectorTab[]).map((tab) => <button key={tab} role="tab" aria-selected={inspectorTab === tab} className={inspectorTab === tab ? "active" : ""} onClick={() => setInspectorTab(tab)}>{tab}</button>)}<button className="collapse-inspector" title="Collapse inspector" aria-label="Collapse inspector" onClick={() => setRightCollapsed(true)}>›</button></div>
        {!model ? <div className="pro-inspector-body"><div className="inspector-note">Open an architecture to inspect operators, topology and lineage.</div></div>
          : inspectorTab === "OPERATOR" ? <OperatorInspector model={model} node={selectedNode} edge={selectedEdge} totalsMatch={totalsMatch} onFocus={focusNode} />
          : inspectorTab === "GRAPH" ? <GraphInspector doc={doc!} model={model} totalsMatch={totalsMatch} onExport={exportFromApi} />
          : <LineageInspector doc={doc!} registryIds={new Set(registryItems.map((item) => item.architecture_id))} onOpen={openDoc} />}
      </aside>}

      <div className="horizontal-resizer" role="separator" aria-orientation="horizontal" aria-label="Resize console" tabIndex={0} onPointerDown={(event) => beginResize("console", event)} onKeyDown={(event) => resizeWithKeys("console", event)}><i /></div>
      <section className="pro-console" aria-label="Diagnostic console">
        <div className="console-tabs" role="tablist">{(["EXPERIMENT LOG", "DIAGNOSTICS", "TENSOR WATCH", "SPEC EDITOR", "WORKERS"] as ConsoleTab[]).map((tab) => <button key={tab} role="tab" aria-selected={consoleTab === tab} className={consoleTab === tab ? "active" : ""} onClick={() => setConsoleTab(tab)}>{tab}{tab === "DIAGNOSTICS" && diagnostics.some((item) => item.level !== "PASS") && <span>{diagnostics.filter((item) => item.level !== "PASS").length}</span>}</button>)}
          <div className="console-spacer" /><span>{consoleTab === "WORKERS" ? "GET /v1/infrastructure/workers" : "SESSION EVENTS"}</span>
          <button title="Clear session log" aria-label="Clear session log" onClick={() => setLog([])}><Icon name="close" /></button></div>
        {consoleTab === "EXPERIMENT LOG" ? <div className="pro-log">{log.length ? log.map((entry, index) => <p key={`${entry.at}-${index}`}><time>{entry.at}</time><b className={entry.level === "PASS" ? "pass" : entry.level === "FAIL" ? "fail" : entry.level === "WARN" ? "warn" : "info"}>{entry.level}</b><span>{entry.message}</span><code>{entry.code ?? ""}</code></p>) : <p><time>—</time><b className="muted">NOTE</b><span>No events yet in this session.</span><code /></p>}</div>
          : consoleTab === "DIAGNOSTICS" ? <div className="pro-log">{diagnostics.map((item) => <p key={item.message}><time>{validation?.at ?? "—"}</time><b className={item.level === "PASS" ? "pass" : item.level === "FAIL" ? "fail" : "warn"}>{item.level}</b><span>{item.message}</span><code>{item.code}</code></p>)}</div>
          : consoleTab === "TENSOR WATCH" ? <TensorWatch model={model} />
          : consoleTab === "SPEC EDITOR" ? <div className="spec-editor">
            <textarea aria-label="Architecture JSON (validated by the API)" spellCheck={false} value={draftText} onChange={(event) => setDraftText(event.target.value)} />
            <div className="spec-actions">
              <button className="button" disabled={specBusy} onClick={() => detail && setDraftText(JSON.stringify(detail.architecture, null, 2))}>Load open graph</button>
              <button className="button" disabled={specBusy} onClick={() => void submitSpec(false)}>Validate</button>
              <button className="button primary" disabled={specBusy} onClick={() => void submitSpec(true)}>Validate and register</button>
              {specMessage && <p className={specMessage.tone} role={specMessage.tone === "fail" ? "alert" : "status"}>{specMessage.text}</p>}
            </div></div>
          : <div className="pro-log">{!workers.loaded ? <p><time>—</time><b className="info">INFO</b><span>Loading workers…</span><code /></p> : workers.error ? <p><time>—</time><b className="fail">FAIL</b><span>{workers.error}</span><code /></p>
            : !workers.data?.configured ? <p><time>—</time><b className="warn">UNAVAILABLE</b><span>Durable worker queue (Redis) is not configured on the API host.</span><code>not_configured</code></p>
            : workers.data.workers.length === 0 ? <p><time>—</time><b className="warn">IDLE</b><span>No worker has reported a heartbeat.</span><code /></p>
            : workers.data.workers.map((worker) => <p key={worker.worker_id}><time>{worker.last_seen.slice(11, 23)}</time><b className="pass">{worker.status.toUpperCase()}</b><span>{worker.hostname} · {shortId(worker.worker_id, 8)}</span><code>{worker.active_job_id ? `job ${shortId(worker.active_job_id, 8)}` : "idle"}</code></p>)}</div>}
      </section>
    </div>
    {contextMenu && model && <div className="node-context-menu" style={{ left: contextMenu.x, top: contextMenu.y }} role="menu">
      <header>NODE / {model.nodes[contextMenu.index].id.toUpperCase()}</header>
      <button role="menuitem" onClick={() => { focusNode(contextMenu.index); setContextMenu(null) }}><Icon name="eye" /> Inspect operator <kbd>↵</kbd></button>
      <button role="menuitem" onClick={() => { setSelectedNodes((current) => Array.from(new Set([...current, contextMenu.index]))); setContextMenu(null) }}><Icon name="compare" /> Add to selection <kbd>⇧</kbd></button>
      <button role="menuitem" onClick={() => { fitSelection([contextMenu.index]); setContextMenu(null) }}><Icon name="fit" /> Fit to node <kbd>F</kbd></button>
      <button role="menuitem" onClick={() => { void navigator.clipboard?.writeText(model.nodes[contextMenu.index].id); setContextMenu(null) }}><Icon name="copy" /> Copy node ID</button>
    </div>}
    {!effectiveRight && <button className="floating-restore-inspector" onClick={() => { setRightCollapsed(false); if (mode === "research") setMode("explore") }} title="Show technical inspector">‹ INSPECTOR</button>}
  </div>
}

type Diagnostic = { level: "PASS" | "FAIL" | "WARN"; message: string; code: string }

export function buildDiagnostics(doc: Doc | undefined, model: GraphModel | null, totalsMatch: boolean, hashMatches: boolean, layoutError: string | null): Diagnostic[] {
  if (!doc) return [{ level: "WARN", message: "No architecture open", code: "W_NO_GRAPH" }]
  const out: Diagnostic[] = []
  const validation = doc.validation
  if (!validation || validation.status === "pending") out.push({ level: "WARN", message: "Validation in progress", code: "W_PENDING" })
  else if (validation.status === "pass") out.push({ level: "PASS", message: "Schema and DAG validation (archai_core)", code: "POST /validate" })
  else if (validation.status === "offline") out.push({ level: "WARN", message: `Validator unreachable: ${validation.error}`, code: "W_OFFLINE" })
  else out.push({ level: "FAIL", message: `Validation rejected the graph: ${validation.error}`, code: "E_INVALID" })
  if (validation?.status === "pass") out.push(hashMatches ? { level: "PASS", message: doc.draft ? "Canonical hash computed (unregistered draft)" : "Canonical hash matches registry id", code: "sha256[:24]" } : { level: "FAIL", message: "Canonical hash differs from registry id", code: "E_HASH" })
  if (layoutError) out.push({ level: "FAIL", message: `Layout failed: ${layoutError}`, code: "E_LAYOUT" })
  else if (model) {
    out.push({ level: "PASS", message: `Acyclic topology · ${model.layers} layers`, code: "layout" })
    out.push(totalsMatch ? { level: "PASS", message: "Per-node analytical costs sum to the API totals", code: "metrics" } : { level: "WARN", message: "Per-node analytical costs differ from API totals", code: "W_METRICS" })
  }
  out.push({ level: "WARN", message: "Latency is not measured: no hardware profiler is connected", code: "W_NO_LATENCY" })
  out.push({ level: "WARN", message: "No trained weights attached: gradient and activation statistics are unavailable", code: "W_NO_WEIGHTS" })
  return out
}

function InspectorSection({ title, rows }: { title: string; rows: [string, string][] }) {
  return <section className="inspector-section"><h3>{title}</h3>{rows.map(([label, value]) => <div key={label}><span>{label}</span><code title={value}>{value}</code></div>)}</section>
}

function OperatorInspector({ model, node, edge, totalsMatch, onFocus }: { model: GraphModel; node: GraphNodeModel | null; edge: GraphEdgeModel | null; totalsMatch: boolean; onFocus: (index: number) => void }) {
  if (edge) {
    const source = model.nodes[edge.from]; const target = model.nodes[edge.to]
    return <div className="pro-inspector-body"><div className="selection-heading"><span>EDGE / {edge.id.toUpperCase()}</span><h2>{source.id} → {target.id}</h2><code>{edge.kind}_connection</code></div>
      <InspectorSection title="TENSOR TRANSPORT" rows={[["Source", `${source.id} (${source.op})`], ["Target", `${target.id} (${target.op})`], ["Tensor shape", formatShape(edge.shape)], ["Data type", "float32 (compiler default)"], ["Connection", edge.kind], ["Layer span", String(edge.span)]]} />
      <InspectorSection title="ANALYTICAL TRANSFER" rows={[["Activation memory", formatBytes(edge.shape[0] * edge.shape[1] * edge.shape[2] * 4)], ["Fan-out of source", `${source.outgoing.length} consumer${source.outgoing.length === 1 ? "" : "s"}`], ["Fan-in of target", `${target.fanIn} input${target.fanIn === 1 ? "" : "s"}${target.fanIn > 1 ? " (mean-reduced)" : ""}`], ["Layout", "NCHW"]]} />
      <div className="inspector-actions"><button className="button" onClick={() => onFocus(edge.from)}>Inspect source</button><button className="button" onClick={() => onFocus(edge.to)}>Inspect target</button></div>
      <div className="inspector-note">Per batch element, float32. Edge shapes are derived from the validated graph; nothing is measured at runtime.</div></div>
  }
  if (!node) return <div className="pro-inspector-body"><div className="inspector-note">Select a node or an edge on the canvas (Shift+click to multi-select). Use the node search to jump to an operator.</div>
    <InspectorSection title="OPERATOR MIX" rows={model.groups.map((group) => [group, `${model.nodes.filter((item) => item.group === group).length} node(s)`])} /></div>
  return <div className="pro-inspector-body"><div className="selection-heading"><span>NODE / N{String(node.index).padStart(2, "0")}</span><h2>{node.id}</h2><code>{node.op}</code></div>
    <InspectorSection title="OPERATOR CONFIGURATION" rows={[["Kernel", node.kernelSize ? `${node.kernelSize} × ${node.kernelSize}` : "—"], ["Stride / padding", node.op.startsWith("conv") || node.op === "avg_pool3x3" ? `1 / ${Math.floor((node.kernelSize ?? 1) / 2)}` : "—"], ["Declared channels", String(node.declaredChannels)], ["Normalization", node.normalization ?? "—"], ["Activation", node.activation ?? "—"], ["Stage group", node.group], ["Layer", String(node.layer)], ["Trainable", node.parameters > 0 ? "True" : "False"]]} />
    <InspectorSection title="TENSOR CONTRACT" rows={[["Input tensor", formatShape(node.inputShape)], ["Output tensor", formatShape(node.outputShape)], ["Incoming edges", `${node.incoming.length} · ${node.incoming.join(", ") || "none"}`], ["Outgoing edges", `${node.outgoing.length} · ${node.outgoing.join(", ") || "none"}`]]} />
    <InspectorSection title="COMPUTE PROFILE · ANALYTICAL" rows={[["Parameters", formatCount(node.parameters)], ["FLOPs", formatCount(node.flops)], ["Output activation", formatBytes(node.activationBytes)], ["Latency", "not measured"], ["Gradient statistics", "no checkpoint attached"]]} />
    <div className="source-block"><header><span>PYTORCH / ARCHAI_COMPILER</span><button title="Copy generated PyTorch" aria-label="Copy generated PyTorch" onClick={() => void navigator.clipboard?.writeText(node.module)}><Icon name="copy" /></button></header><pre>{node.module}</pre></div>
    <div className="provenance-block"><span>METRIC PROVENANCE</span><p>Analytical: computed from the validated graph with the archai_compiler.metrics formulas{totalsMatch ? "; per-node values sum to the API totals." : "."} Not trained, not profiled.</p></div></div>
}

function GraphInspector({ doc, model, totalsMatch, onExport }: { doc: Doc; model: GraphModel; totalsMatch: boolean; onExport: (format: "json" | "pytorch") => void }) {
  const detail = doc.detail!
  const architecture = detail.architecture
  return <div className="pro-inspector-body"><div className="selection-heading"><span>GRAPH / {doc.draft ? "UNREGISTERED DRAFT" : "REGISTERED SPEC"}</span><h2>{shortId(detail.hash, 16)}</h2><code title={detail.hash}>hash:{detail.hash}</code></div>
    <InspectorSection title="TOPOLOGY" rows={[["Nodes", `${architecture.nodes.length} operators`], ["Edges", `${architecture.edges.length} directed`], ["Residual paths", String(model.residualCount)], ["Branch edges", String(model.branchCount)], ["Depth (layers)", String(model.layers)], ["Stage groups", String(model.groups.length)], ["Validation", doc.validation?.status ?? "pending"]]} />
    <InspectorSection title="MODEL CONFIGURATION" rows={[["Search space", architecture.search_space ?? "—"], ["Schema version", architecture.schema_version ?? "1.0"], ["Input shape", `[B, ${architecture.input_spec.channels}, ${architecture.input_spec.height}, ${architecture.input_spec.width}]`], ["Classes", String(architecture.output_classes)], ["Generator", architecture.generator_version ?? "—"], ["Fan-in reduction", architecture.metadata?.fan_in_reduction ?? "mean"]]} />
    <InspectorSection title="TOTAL COST · ANALYTICAL (API)" rows={[["Parameters", formatCount(detail.analytical_metrics.parameters)], ["FLOPs", formatCount(detail.analytical_metrics.flops)], ["Activation peak", formatBytes(detail.analytical_metrics.activation_memory_bytes)], ["Graph-model agreement", totalsMatch ? "✓ matches" : "differs"], ["Latency", "not measured"]]} />
    {doc.draft ? <div className="inspector-note">Drafts are validated but not stored. Register the spec to enable canonical JSON and TorchScript exports.</div>
      : <div className="inspector-actions"><button className="button" onClick={() => onExport("json")}><Icon name="download" /> Export JSON</button><button className="button" onClick={() => onExport("pytorch")}><Icon name="download" /> Export PyTorch (TorchScript)</button></div>}
  </div>
}

function LineageInspector({ doc, registryIds, onOpen }: { doc: Doc; registryIds: Set<string>; onOpen: (id: string) => void }) {
  const architecture = doc.detail!.architecture
  const lineage = architecture.lineage ?? []
  const metadata = Object.entries(architecture.metadata ?? {})
  return <div className="pro-inspector-body"><div className="selection-heading"><span>LINEAGE / {lineage.length} ANCESTOR{lineage.length === 1 ? "" : "S"}</span><h2>{shortId(doc.detail!.hash, 16)}</h2><code>{architecture.generator_version ?? "manual"}</code></div>
    {lineage.length ? <div className="lineage-chain">{lineage.map((ancestor, index) => {
      const known = registryIds.has(ancestor)
      return <button key={`${ancestor}-${index}`} disabled={!known} onClick={() => known && onOpen(ancestor)} title={known ? "Open ancestor" : "Ancestor is not in the registry"}><i /><span><small>ANCESTOR {index + 1}{known ? "" : " · NOT REGISTERED"}</small><b>{shortId(ancestor, 16)}</b><code>{known ? "registered" : "recorded id only"}</code></span></button>
    })}<div className="lineage-current"><i /><span><small>SELECTED</small><b>{shortId(doc.detail!.hash, 16)}</b><code>{architecture.search_space}</code></span></div></div>
      : <div className="inspector-note">No lineage recorded for this architecture (lineage is empty in the stored spec). Lineage is filled when a search or generator derives a candidate from parents.</div>}
    <InspectorSection title="REPRODUCIBILITY" rows={[["Search space", architecture.search_space ?? "—"], ["Generator version", architecture.generator_version ?? "—"], ["Seed", architecture.seed === null || architecture.seed === undefined ? "not recorded" : String(architecture.seed)], ["Canonical hash", shortId(doc.detail!.hash, 24)]]} />
    {metadata.length ? <InspectorSection title="METADATA" rows={metadata.map(([key, value]) => [key, value])} /> : null}
  </div>
}

function TensorWatch({ model }: { model: GraphModel | null }) {
  if (!model) return <div className="tensor-watch"><div><span>WATCH</span><span>SHAPE</span><span>PARAMS</span><span>FLOPs</span><span>ACT. MEMORY</span></div></div>
  return <div className="tensor-watch"><div><span>WATCH</span><span>OUTPUT SHAPE</span><span>PARAMS</span><span>FLOPs</span><span>ACT. MEMORY</span></div>
    {model.nodes.map((node) => <div key={node.id}><code>{node.id}.output</code><code>{formatShape(node.outputShape)}</code><code>{formatCount(node.parameters)}</code><code>{formatCompact(node.flops)}</code><code>{formatBytes(node.activationBytes)}</code></div>)}
    <p className="tensor-note">Analytical values from the graph. Runtime mean / std / gradient norms need a trained checkpoint and are not shown.</p></div>
}
