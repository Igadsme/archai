"use client"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { items, usePoll } from "../components/usePoll"
import { useSelectedProject } from "../components/ProjectPicker"
import { apiBase, downloadJson, getApiKey, setApiKey } from "../lib/api"
import { PROJECT_EVENT } from "../lib/project"
import type { JobItem, Readiness, ResearchProject } from "../lib/types"
import { healthResponse, itemsResponse } from "../lib/validators"
import { CommandPalette, navigationCommands, type Command } from "./CommandPalette"
import { ErrorBoundary } from "./ErrorBoundary"
import { Icon } from "./Icon"
import { hrefFor, SCREENS, screenForPath, type View } from "./navigation"

export const STUDIO_VERSION = process.env.NEXT_PUBLIC_STUDIO_VERSION ?? "dev"

export function StudioShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const current = screenForPath(pathname)
  const health = usePoll<{ status: string; evidence_policy?: string }>("/health", 10_000, healthResponse)
  const readiness = usePoll<Readiness>("/readiness", 15_000)
  const jobs = usePoll<{ items: JobItem[] }>("/v1/jobs", 10_000, itemsResponse)
  const projects = usePoll<{ items: ResearchProject[] }>("/v1/projects", 30_000, itemsResponse)
  const { projectId, select } = useSelectedProject()
  const refreshProjects = projects.refresh
  const [key, setKey] = useState("")
  const [toast, setToast] = useState("")
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [keyOpen, setKeyOpen] = useState(false)
  const toastTimer = useRef<number | undefined>(undefined)
  useEffect(() => setKey(getApiKey()), [])

  const online = health.loaded && !health.error && health.data?.status === "ok"
  const apiState = !health.loaded ? "CHECKING" : online ? "CONNECTED" : "OFFLINE"
  const failedJobs = items(jobs.data).filter((job) => job.status === "failed").length
  const runningJobs = items(jobs.data).filter((job) => job.status === "running" || job.status === "queued").length
  const host = useMemo(() => { try { return new URL(apiBase).host } catch { return apiBase } }, [])

  const go = useCallback((view: View) => router.push(hrefFor(view)), [router])
  const notify = useCallback((message: string) => {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(""), 3200)
  }, [])
  const exportWorkspace = useCallback(() => {
    downloadJson("archai-workspace-status.json", {
      exported_at: new Date().toISOString(), studio_version: STUDIO_VERSION, api_url: apiBase, screen: current.id,
      health: health.data ?? { error: health.error }, readiness: readiness.data ?? { error: readiness.error },
      jobs: { total: items(jobs.data).length, active: runningJobs, failed: failedJobs }, selected_project: projectId || null,
      evidence: "Live API responses at export time; no illustrative data.",
    })
    notify("Workspace status exported as JSON")
  }, [current.id, failedJobs, health.data, health.error, jobs.data, notify, projectId, readiness.data, readiness.error, runningJobs])

  const commands: Command[] = useMemo(() => [
    ...navigationCommands(go),
    { id: "export", label: "Export workspace status", detail: "Download live health, readiness and job counts as JSON", group: "ACTION", icon: "download", shortcut: "E", run: exportWorkspace },
    { id: "backend", label: "Backend connection status", detail: `GET ${host}/health`, group: "ACTION", icon: "database",
      run: () => notify(online ? `CONNECTED — ${host} answered /health (${readiness.data?.status ?? "readiness unknown"})` : `OFFLINE — ${health.error ?? "no answer from /health"}`) },
    { id: "refresh", label: "Refresh connection", detail: "Re-run health, readiness and job polls now", group: "ACTION", icon: "refresh", run: () => { health.refresh(); readiness.refresh(); jobs.refresh() } },
  ], [exportWorkspace, go, health, host, jobs, notify, online, readiness])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen((value) => !value) }
    }
    const onNotice = (event: Event) => notify((event as CustomEvent<string>).detail)
    window.addEventListener("keydown", onKey)
    window.addEventListener("archai:notice", onNotice)
    window.addEventListener(PROJECT_EVENT, refreshProjects)
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("archai:notice", onNotice); window.removeEventListener(PROJECT_EVENT, refreshProjects) }
  }, [notify, refreshProjects])

  const keyField = <label className="api-key-field"><span><Icon name="key" size={12} /> API KEY <em>this browser session only</em></span>
    <input type="password" aria-label="API key (kept for this browser session only)" value={key} autoComplete="off" placeholder="optional in local mode"
      onChange={(event) => { setKey(event.target.value); setApiKey(event.target.value) }} /></label>
  const activeProjects = items(projects.data).filter((project) => project.status === "active")
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark" aria-hidden="true">A<span>/</span></div><div><strong>ArchAI</strong><small>STUDIO</small></div></div>
      <label className="workspace-select"><span>RESEARCH PROJECT</span>
        <select aria-label="Research project" value={projectId} onChange={(event) => select(event.target.value)}>
          <option value="">{projects.error ? "Projects unavailable" : activeProjects.length ? "No project selected" : "No projects yet"}</option>
          {activeProjects.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}
        </select>
      </label>
      <nav aria-label="Studio screens">{SCREENS.map((screen) => <div key={screen.id}>
        {screen.section && <div className="nav-divider">{screen.section}</div>}
        <Link href={screen.href} className={current.id === screen.id ? "active" : ""} aria-current={current.id === screen.id ? "page" : undefined} title={screen.title}>
          <Icon name={screen.icon} /><span>{screen.label}</span>
          {screen.id === "training" && runningJobs > 0 && <i className="nav-live" aria-label={`${runningJobs} active jobs`} />}
          {screen.id === "experiments" && failedJobs > 0 && <em title="Failed jobs">{failedJobs}</em>}
        </Link>
      </div>)}</nav>
      <div className="sidebar-bottom">
        <button className="cluster-state" onClick={() => go("system")} title="Open system administration">
          <i className={online ? "" : "offline"} /><span><b>{online ? "API connected" : apiState === "CHECKING" ? "Checking API" : "API unavailable"}</b><small>{host}{readiness.data ? ` · ${readiness.data.status}` : ""}</small></span><Icon name="chevron" size={14} />
        </button>
        {keyField}
      </div>
    </aside>
    <header className="topbar">
      <div className="breadcrumb"><span>ARCHAI</span><i>/</i><span>RESEARCH</span><i>/</i><b>{current.title.toUpperCase()}</b></div>
      <div className="top-actions">
        <span className={`illustrative ${online ? "live" : "offline"}`} role="status">{online ? "LIVE API DATA" : apiState === "CHECKING" ? "CONNECTING" : "API OFFLINE"}</span>
        <button className="command" onClick={() => setPaletteOpen(true)} aria-label="Search commands (Ctrl+K)"><kbd>⌘</kbd><span>Search commands</span><kbd>K</kbd></button>
        <button className="icon-button" title="Experiment history" aria-label="Experiment history" onClick={() => go("experiments")}><Icon name="clock" />{failedJobs > 0 && <i className="notification-dot" />}</button>
        <button className="icon-button narrow-only" aria-label="API key" aria-expanded={keyOpen} title="API key" onClick={() => setKeyOpen((value) => !value)}><Icon name="key" />{key ? <i className="notification-dot key-set" /> : null}</button>
        <button className="button compact" onClick={exportWorkspace}><Icon name="download" /> Export</button>
      </div>
      {keyOpen ? <div className="key-popover narrow-only" role="dialog" aria-label="API key">{keyField}<button className="button compact" onClick={() => setKeyOpen(false)}>Done</button></div> : null}
    </header>
    <main className="main-content" id="main">
      <ErrorBoundary scope={current.id}>{children}</ErrorBoundary>
    </main>
    <footer className="statusbar">
      <div><span><i className={online ? "online-dot" : "offline-dot"} /> {apiState}</span><span>ARCHAI STUDIO / {current.label.toUpperCase()}</span><span>API {host}</span></div>
      <div><span><Icon name="terminal" size={12} /> {failedJobs} FAILED JOBS</span><span><Icon name="database" size={12} /> {readiness.data ? `READINESS ${readiness.data.status.toUpperCase()}` : "READINESS —"}</span><span>STUDIO {STUDIO_VERSION}</span></div>
    </footer>
    <CommandPalette open={paletteOpen} commands={commands} onClose={() => setPaletteOpen(false)} />
    {toast && <div className={`toast ${toast.startsWith("UNAVAILABLE") || toast.startsWith("OFFLINE") ? "toast-warn" : ""}`} role="status"><Icon name={toast.startsWith("UNAVAILABLE") ? "alert" : "check"} /> {toast}</div>}
  </div>
}
