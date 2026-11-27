export const apiBase = process.env.NEXT_PUBLIC_ARCHAI_API_URL ?? "http://127.0.0.1:8000"
const KEY_STORAGE = "archai.apiKey"

export function getApiKey(): string {
  if (typeof window === "undefined") return ""
  return window.sessionStorage.getItem(KEY_STORAGE) ?? ""
}

export function setApiKey(value: string): void {
  if (typeof window === "undefined") return
  if (value) window.sessionStorage.setItem(KEY_STORAGE, value)
  else window.sessionStorage.removeItem(KEY_STORAGE)
}

export type FetchOutcome<T> = { ok: true; data: T } | { ok: false; status: number; detail: string }

function detailOf(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail
    return typeof detail === "string" ? detail : JSON.stringify(detail)
  }
  return fallback
}

/** GET with error details preserved, so pages can say why something is unavailable. */
export async function fetchJson<T>(path: string): Promise<FetchOutcome<T>> {
  const key = getApiKey()
  try {
    const response = await fetch(`${apiBase}${path}`, { headers: key ? { "x-api-key": key } : {} })
    const data = await response.json().catch(() => null) as unknown
    if (response.ok) return { ok: true, data: data as T }
    return { ok: false, status: response.status, detail: detailOf(data, response.statusText) }
  } catch (error) {
    return { ok: false, status: 0, detail: error instanceof Error ? `API unreachable (${error.message})` : "API unreachable" }
  }
}

export async function getJson<T>(path: string): Promise<T | null> {
  const outcome = await fetchJson<T>(path)
  return outcome.ok ? outcome.data : null
}

/** Download a binary/JSON export as a browser file; returns an error message or null. */
export async function downloadFile(path: string, fallbackName: string): Promise<string | null> {
  const key = getApiKey()
  try {
    const response = await fetch(`${apiBase}${path}`, { headers: key ? { "x-api-key": key } : {} })
    if (!response.ok) {
      const data = await response.json().catch(() => null) as unknown
      return `${response.status}: ${detailOf(data, response.statusText)}`
    }
    const blob = await response.blob()
    const disposition = response.headers.get("content-disposition") ?? ""
    const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url; anchor.download = name; anchor.click()
    URL.revokeObjectURL(url)
    return null
  } catch (error) {
    return error instanceof Error ? error.message : "download failed"
  }
}

export type PostOutcome<T> = { ok: true; data: T } | { ok: false; status: number; detail: string }

export async function postJson<T>(path: string, body: unknown): Promise<PostOutcome<T>> {
  const key = getApiKey()
  try {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", ...(key ? { "x-api-key": key } : {}) }, body: JSON.stringify(body),
    })
    const data = await response.json().catch(() => null) as unknown
    if (response.ok) return { ok: true, data: data as T }
    return { ok: false, status: response.status, detail: detailOf(data, response.statusText) }
  } catch (error) {
    return { ok: false, status: 0, detail: error instanceof Error ? error.message : "network error" }
  }
}
