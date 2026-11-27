"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { getApiKey, setApiKey } from "../lib/api"
import { type Poll, usePoll } from "./usePoll"

/** The ten Studio pages named in Imani's spec (docs/SPEC_ACCEPTANCE.md, §10). */
export const PAGES = [
  { href: "/", label: "Research Dashboard" },
  { href: "/generator", label: "Architecture Generator" },
  { href: "/explorer", label: "Architecture Graph Explorer" },
  { href: "/search", label: "Autonomous Search Laboratory" },
  { href: "/pareto", label: "Pareto Optimization Explorer" },
  { href: "/training", label: "Training Laboratory" },
  { href: "/compare", label: "Model Comparison" },
  { href: "/results", label: "Research Results" },
  { href: "/models", label: "Model Registry" },
  { href: "/admin", label: "System Administration" },
] as const

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const health = usePoll<{ status: string }>("/health", 10000)
  const [key, setKey] = useState("")
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => setKey(getApiKey()), [])
  useEffect(() => setMenuOpen(false), [pathname])
  const apiState = !health.loaded ? "checking" : health.data?.status === "ok" ? "ready" : "unavailable"
  return <div className="shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="sidebar">
      <div className="brand-row">
        <div><p className="eyebrow">ARCHAI STUDIO</p><h1>AI that designs AI.</h1></div>
        <button className="menu-toggle" aria-expanded={menuOpen} aria-controls="primary-nav" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "Close" : "Menu"}</button>
      </div>
      <p className="muted tagline">Evidence-aware neural architecture research.</p>
      <nav id="primary-nav" aria-label="Studio pages" className={menuOpen ? "open" : undefined}>
        {PAGES.map((page) => <Link key={page.href} href={page.href} aria-current={pathname === page.href ? "page" : undefined}
          className={pathname === page.href ? "active" : undefined}>{page.label}</Link>)}
      </nav>
      <div className="status" role="status"><span className={`dot ${apiState}`} aria-hidden="true" /> API {apiState}{health.error ? ` (${health.error})` : ""}</div>
      <label className="key-field"><span className="label">API key (kept for this browser session only)</span>
        <input type="password" value={key} autoComplete="off" placeholder="optional in local mode" onChange={(event) => { setKey(event.target.value); setApiKey(event.target.value) }} /></label>
    </aside>
    <main className="content" id="main">{children}</main>
  </div>
}

export function PageHeader({ eyebrow, title, note }: { eyebrow: string; title: string; note?: string }) {
  return <header className="topbar"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2>{note ? <small>{note}</small> : null}</div><span className="badge">No fabricated metrics</span></header>
}

export function Empty({ children }: { children: React.ReactNode }) { return <div className="empty">{children}</div> }

export function Errors({ errors }: { errors: string[] }) {
  return errors.length ? <ul className="errors" role="alert">{errors.map((error) => <li key={error}>{error}</li>)}</ul> : null
}

/** A feature that is intentionally not implemented (or not available on this host), stated plainly. */
export function Unavailable({ feature, reason }: { feature: string; reason: string }) {
  return <div className="unavailable" role="note"><strong>Unavailable: {feature}</strong><span>{reason}</span></div>
}

/** Loading / error / empty states for a polled resource; renders children only with data. */
export function Loaded<T>({ poll, empty, isEmpty, children }: { poll: Poll<T>; empty?: string; isEmpty?: (data: T) => boolean; children: (data: T) => React.ReactNode }) {
  if (!poll.loaded) return <p className="muted" role="status">Loading…</p>
  if (poll.error || poll.data === null) return <div className="errors" role="alert">Could not load: {poll.error ?? "no data"}</div>
  if (isEmpty?.(poll.data)) return <Empty>{empty ?? "Nothing recorded yet."}</Empty>
  return <>{children(poll.data)}</>
}
