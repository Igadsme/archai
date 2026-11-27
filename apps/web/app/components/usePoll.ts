"use client"
import { useCallback, useEffect, useState } from "react"
import { request, type ApiErrorKind, type Validator } from "../lib/api"

export type Poll<T> = { data: T | null; loaded: boolean; error: string | null; errorKind: ApiErrorKind | null; status: number; refresh: () => void }

/**
 * Poll a GET endpoint. In-flight requests are cancelled on unmount or path change, and `error` carries the
 * API's reason (status + detail) when a load fails. Polling pauses while the tab is hidden.
 */
export function usePoll<T>(path: string | null, intervalMs = 5000, validate?: Validator): Poll<T> {
  const [data, setData] = useState<T | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorKind, setErrorKind] = useState<ApiErrorKind | null>(null)
  const [status, setStatus] = useState(0)
  const [tick, setTick] = useState(0)
  const [apiKeyVersion, setApiKeyVersion] = useState(0)
  useEffect(() => {
    const onKey = () => setApiKeyVersion((value) => value + 1)
    window.addEventListener("archai:api-key", onKey)
    return () => window.removeEventListener("archai:api-key", onKey)
  }, [])
  useEffect(() => {
    if (!path) { setData(null); setLoaded(false); setError(null); return }
    let controller: AbortController | null = null
    let active = true
    let first = true
    const load = async () => {
      if (controller || (!first && document.visibilityState === "hidden")) return
      first = false
      controller = new AbortController()
      const result = await request<T>(path, { signal: controller.signal, validate })
      controller = null
      if (!active) return
      if (result.ok) { setData(result.data); setError(null); setErrorKind(null); setStatus(result.status) }
      else if (result.error.kind !== "aborted") { setData(null); setError(result.error.message); setErrorKind(result.error.kind); setStatus(result.status) }
      setLoaded(true)
    }
    void load()
    const timer = intervalMs > 0 ? window.setInterval(() => void load(), intervalMs) : undefined
    return () => { active = false; controller?.abort(); if (timer) window.clearInterval(timer) }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- validators are module-level constants
  }, [path, intervalMs, tick, apiKeyVersion])
  const refresh = useCallback(() => setTick((value) => value + 1), [])
  return { data, loaded, error, errorKind, status, refresh }
}

export const items = <T,>(value: { items?: T[] } | null): T[] => value?.items ?? []
