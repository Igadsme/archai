"use client"
import { useEffect, useMemo, useRef, useState } from "react"
import { Icon, type IconName } from "./Icon"
import { SCREENS, type View } from "./navigation"

export type Command = {
  id: string
  label: string
  detail: string
  group: "NAVIGATE" | "WORKSPACE" | "ACTION"
  icon: IconName
  shortcut?: string
  run: () => void
}

export function filterCommands(commands: Command[], query: string): Command[] {
  const needle = query.trim().toLowerCase()
  return needle ? commands.filter((command) => `${command.label} ${command.detail} ${command.group}`.toLowerCase().includes(needle)) : commands
}

export function CommandPalette({ open, commands, onClose }: { open: boolean; commands: Command[]; onClose: () => void }) {
  const [query, setQuery] = useState("")
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const filtered = useMemo(() => filterCommands(commands, query), [commands, query])

  useEffect(() => {
    if (!open) return
    setQuery("")
    setActive(0)
    queueMicrotask(() => input.current?.focus())
  }, [open])

  if (!open) return null
  const execute = (command: Command) => { command.run(); onClose() }
  return <div className="palette-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette">
      <label><Icon name="search" /><input ref={input} value={query} aria-label="Search commands" onChange={(event) => { setQuery(event.target.value); setActive(0) }} onKeyDown={(event) => {
        if (event.key === "Escape") onClose()
        if (event.key === "ArrowDown") { event.preventDefault(); setActive((value) => Math.min(filtered.length - 1, value + 1)) }
        if (event.key === "ArrowUp") { event.preventDefault(); setActive((value) => Math.max(0, value - 1)) }
        if (event.key === "Enter" && filtered[active]) execute(filtered[active])
      }} placeholder="Navigate, change workspace, or run an action…" /><kbd>ESC</kbd></label>
      <div className="palette-results" role="listbox" aria-label="Commands">
        {filtered.length ? filtered.map((command, index) => <button key={command.id} role="option" aria-selected={index === active} className={index === active ? "active" : ""} onMouseEnter={() => setActive(index)} onClick={() => execute(command)}>
          <span><Icon name={command.icon} /></span><span><b>{command.label}</b><small>{command.detail}</small></span><em>{command.group}</em>{command.shortcut && <kbd>{command.shortcut}</kbd>}
        </button>) : <div className="palette-empty"><Icon name="search" /><span>No matching command</span><small>Try a screen name or workspace action.</small></div>}
      </div>
      <footer><span><kbd>↑</kbd><kbd>↓</kbd> SELECT</span><span><kbd>↵</kbd> RUN</span><span>LOCAL COMMANDS</span></footer>
    </section>
  </div>
}

export function navigationCommands(go: (view: View) => void): Command[] {
  return SCREENS.map((screen) => ({ id: `go-${screen.id}`, label: screen.title, detail: screen.detail, group: "NAVIGATE" as const, icon: screen.icon, run: () => go(screen.id) }))
}
