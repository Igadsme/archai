"use client"
import type { ReactNode } from "react"
import type { Poll } from "../components/usePoll"
import { Icon } from "./Icon"

export type Tone = "teal" | "amber" | "red" | "blue" | "gray"

export function Status({ children, tone = "teal" }: { children: ReactNode; tone?: Tone }) {
  return <span className={`status status-${tone}`}><i />{children}</span>
}

export function Panel({ title, meta, children, className = "", actions, id }: { title: string; meta?: string; children: ReactNode; className?: string; actions?: ReactNode; id?: string }) {
  return <section className={`panel ${className}`} aria-label={title} id={id}>
    <header className="panel-header">
      <div><span className="panel-title">{title}</span>{meta && <span className="panel-meta">{meta}</span>}</div>
      {actions && <div className="panel-actions">{actions}</div>}
    </header>
    {children}
  </section>
}

export function PageHeader({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <div className="page-header">
    <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
    <div className="page-actions">{children}</div>
  </div>
}

/** Sparkline over a measured series; renders nothing for fewer than two points. */
export function Sparkline({ values, color = "#5fc8c1", fill = false }: { values: number[]; color?: string; fill?: boolean }) {
  if (values.length < 2) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${34 - ((value - min) / (max - min || 1)) * 28}`).join(" ")
  return <svg className="sparkline" viewBox="0 0 100 38" preserveAspectRatio="none" aria-hidden="true">
    {fill && <polygon points={`0,38 ${points} 100,38`} fill={color} opacity=".08" />}
    <polyline points={points} fill="none" stroke={color} strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
  </svg>
}

/** A capability that is not available on this deployment, stated plainly with the reason. */
export function Unavailable({ feature, reason, children }: { feature: string; reason: string; children?: ReactNode }) {
  return <div className="unavailable-state" role="note">
    <Icon name="alert" />
    <div><b>UNAVAILABLE — {feature}</b><p>{reason}</p>{children}</div>
  </div>
}

export function ErrorList({ errors }: { errors: string[] }) {
  return errors.length ? <ul className="inline-errors" role="alert">{errors.map((error) => <li key={error}><Icon name="alert" size={12} /><span>{error}</span></li>)}</ul> : null
}

export function Notice({ children }: { children: ReactNode }) {
  return children ? <p className="inline-notice" role="status">{children}</p> : null
}

export function EmptyState({ icon = "database", title, children, tall = false }: { icon?: Parameters<typeof Icon>[0]["name"]; title: string; children?: ReactNode; tall?: boolean }) {
  return <div className={`empty-state compact-empty ${tall ? "tall" : ""}`}><div className="empty-grid"><Icon name={icon} size={28} /></div><h3>{title}</h3>{children}</div>
}

/** Loading / failure / empty states for a polled endpoint; renders children only with data. */
export function Loaded<T>({ poll, empty, isEmpty, children, label }: { poll: Poll<T>; empty?: ReactNode; isEmpty?: (data: T) => boolean; children: (data: T) => ReactNode; label?: string }) {
  if (!poll.loaded) return <div className="loading-state" role="status"><i />Loading{label ? ` ${label}` : ""}…</div>
  if (poll.error || poll.data === null) return <div className="load-error" role="alert"><Icon name="alert" size={13} /><span>Could not load{label ? ` ${label}` : ""}: {poll.error ?? "no data"}</span><button className="button compact" onClick={poll.refresh}><Icon name="refresh" size={12} /> Retry</button></div>
  if (isEmpty?.(poll.data)) return <div className="empty-inline">{empty ?? "Nothing recorded yet."}</div>
  return <>{children(poll.data)}</>
}

export const formatCount = (value: number | null | undefined): string => typeof value === "number" && Number.isFinite(value) ? new Intl.NumberFormat("en-US").format(value) : "—"

/** 1234567 → "1.23M"; keeps exact counts available via formatCount for tooltips. */
export function formatCompact(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—"
  const abs = Math.abs(value)
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}G`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${(value / 1e3).toFixed(2)}K`
  return String(value)
}

export function formatBytes(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—"
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GiB`
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(2)} MiB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KiB`
  return `${value} B`
}

export const shortId = (value: string | null | undefined, length = 12): string => value ? value.slice(0, length) : "—"

export function statusTone(status: string | undefined): Tone {
  switch (status) {
    case "running": return "teal"
    case "queued": return "amber"
    case "succeeded": case "completed": return "blue"
    case "failed": return "red"
    default: return "gray"
  }
}
