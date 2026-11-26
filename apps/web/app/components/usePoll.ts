"use client"
import { useEffect, useState } from "react"
import { fetchJson } from "../lib/api"

export type Poll<T> = { data: T | null; loaded: boolean; error: string | null; refresh: () => void }

/** Poll a GET endpoint. `error` carries the API's reason (status + detail) when a load fails. */
export function usePoll<T>(path: string | null, intervalMs = 5000): Poll<T> {
  const [data, setData] = useState<T | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!path) return
    let active = true
    const load = async () => {
      const outcome = await fetchJson<T>(path)
      if (!active) return
      if (outcome.ok) { setData(outcome.data); setError(null) } else { setData(null); setError(outcome.status ? `${outcome.status}: ${outcome.detail}` : outcome.detail) }
      setLoaded(true)
    }
    void load()
    const timer = intervalMs > 0 ? window.setInterval(() => void load(), intervalMs) : undefined
    return () => { active = false; if (timer) window.clearInterval(timer) }
  }, [path, intervalMs, tick])
  return { data, loaded, error, refresh: () => setTick((value) => value + 1) }
}

export const items = <T,>(value: { items?: T[] } | null): T[] => value?.items ?? []
