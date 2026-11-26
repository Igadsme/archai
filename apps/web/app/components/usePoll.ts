"use client"
import { useEffect, useState } from "react"
import { getJson } from "../lib/api"

/** Poll a GET endpoint; `null` data means the API was unreachable or returned an error. */
export function usePoll<T>(path: string, intervalMs = 5000): { data: T | null; loaded: boolean; refresh: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let active = true
    const load = async () => { const value = await getJson<T>(path); if (active) { setData(value); setLoaded(true) } }
    void load()
    const timer = window.setInterval(() => void load(), intervalMs)
    return () => { active = false; window.clearInterval(timer) }
  }, [path, intervalMs, tick])
  return { data, loaded, refresh: () => setTick((value) => value + 1) }
}

export const items = <T,>(value: { items?: T[] } | null): T[] => value?.items ?? []
