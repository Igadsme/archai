"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { getApiKey, setApiKey } from "../lib/api"
import { usePoll } from "./usePoll"

export const PAGES = [
  { href: "/", label: "Overview" },
  { href: "/generator", label: "Generator" },
  { href: "/search", label: "Search lab" },
  { href: "/training", label: "Training jobs" },
  { href: "/experiments", label: "Experiments" },
  { href: "/architectures", label: "Architecture explorer" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/models", label: "Model registry" },
  { href: "/datasets", label: "Datasets" },
  { href: "/infrastructure", label: "Infrastructure" },
] as const

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const health = usePoll<{ status: string }>("/health", 10000)
  const [key, setKey] = useState("")
  useEffect(() => setKey(getApiKey()), [])
  const apiState = !health.loaded ? "checking" : health.data?.status === "ok" ? "ready" : "unavailable"
  return <div className="shell">
    <aside className="sidebar">
      <p className="eyebrow">ARCHAI STUDIO</p><h1>AI that designs AI.</h1><p className="muted">Evidence-aware neural architecture research.</p>
      <nav>{PAGES.map((page) => <Link key={page.href} href={page.href} className={pathname === page.href ? "active" : undefined}>{page.label}</Link>)}</nav>
      <div className="status"><span className={`dot ${apiState}`} /> API {apiState}</div>
      <label className="key-field"><span className="label">API key (session only)</span>
        <input type="password" value={key} placeholder="optional in local mode" onChange={(event) => { setKey(event.target.value); setApiKey(event.target.value) }} /></label>
    </aside>
    <section className="content">{children}</section>
  </div>
}

export function PageHeader({ eyebrow, title, note }: { eyebrow: string; title: string; note?: string }) {
  return <header className="topbar"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2>{note ? <small>{note}</small> : null}</div><span className="badge">No fabricated metrics</span></header>
}

export function Empty({ children }: { children: React.ReactNode }) { return <div className="empty">{children}</div> }

export function Errors({ errors }: { errors: string[] }) {
  return errors.length ? <ul className="errors" role="alert">{errors.map((error) => <li key={error}>{error}</li>)}</ul> : null
}
