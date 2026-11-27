"use client"
import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"
import { hrefFor, type View } from "./navigation"

/** Navigate to a Studio screen, optionally with query parameters (e.g. an architecture id). */
export function useGo() {
  const router = useRouter()
  return useCallback((view: View, params?: Record<string, string>) => {
    const query = params ? `?${new URLSearchParams(params).toString()}` : ""
    router.push(`${hrefFor(view)}${query}`)
  }, [router])
}

/** Read a query parameter on the client without forcing a Suspense boundary for useSearchParams. */
export function useQueryParam(name: string): string | null {
  const [value, setValue] = useState<string | null>(null)
  useEffect(() => { setValue(new URLSearchParams(window.location.search).get(name)) }, [name])
  return value
}
