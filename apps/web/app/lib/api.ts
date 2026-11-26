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

export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${apiBase}${path}`)
    return response.ok ? (await response.json() as T) : null
  } catch { return null }
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
    const detail = data && typeof data === "object" && "detail" in data ? JSON.stringify((data as { detail: unknown }).detail) : response.statusText
    return { ok: false, status: response.status, detail }
  } catch (error) {
    return { ok: false, status: 0, detail: error instanceof Error ? error.message : "network error" }
  }
}
