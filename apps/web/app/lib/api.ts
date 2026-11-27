/**
 * Typed client for the ArchAI FastAPI service.
 *
 * The base URL comes from NEXT_PUBLIC_ARCHAI_API_URL (inlined at build time); the CSP connect-src in
 * next.config.mjs is derived from the same variable. The optional API key is typed by the user, kept in
 * sessionStorage for the browser session only, and sent as x-api-key; it is never bundled.
 */
export const DEFAULT_API_URL = "http://127.0.0.1:8000"
export const DEFAULT_TIMEOUT_MS = 15_000
const KEY_STORAGE = "archai.apiKey"

export function resolveApiBase(raw: string | undefined): string {
  const value = (raw ?? "").trim() || DEFAULT_API_URL
  const url = new URL(value)
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error(`NEXT_PUBLIC_ARCHAI_API_URL must be http(s): ${value}`)
  return value.replace(/\/+$/, "")
}

export const apiBase = resolveApiBase(process.env.NEXT_PUBLIC_ARCHAI_API_URL)

export function getApiKey(): string {
  if (typeof window === "undefined") return ""
  return window.sessionStorage.getItem(KEY_STORAGE) ?? ""
}

export function setApiKey(value: string): void {
  if (typeof window === "undefined") return
  if (value) window.sessionStorage.setItem(KEY_STORAGE, value)
  else window.sessionStorage.removeItem(KEY_STORAGE)
  window.dispatchEvent(new Event("archai:api-key"))
}

export type ApiErrorKind = "network" | "timeout" | "aborted" | "http" | "invalid_response"

export class ApiError extends Error {
  constructor(public readonly kind: ApiErrorKind, public readonly status: number, public readonly detail: string, public readonly body: unknown = null) {
    super(kind === "http" ? `${status}: ${detail}` : detail)
    this.name = "ApiError"
  }
  /** The API answered that a capability is not configured on this host (e.g. no generator checkpoint). */
  get unavailable(): boolean { return this.kind === "http" && this.status === 503 }
  get unauthorized(): boolean { return this.kind === "http" && (this.status === 401 || this.status === 403) }
}

export type ApiResult<T> = { ok: true; data: T; status: number; headers: Headers } | { ok: false; error: ApiError; status: number; detail: string }

/** Runtime check for a response body; return a message describing the mismatch, or null when the body is valid. */
export type Validator = (value: unknown) => string | null

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE"
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
  validate?: Validator
  apiKey?: string
  fetchImpl?: typeof fetch
  baseUrl?: string
}

export function detailOf(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail
    return typeof detail === "string" ? detail : JSON.stringify(detail)
  }
  return fallback || "request failed"
}

async function send(path: string, options: RequestOptions): Promise<{ response: Response } | { error: ApiError }> {
  const controller = new AbortController()
  let timedOut = false
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const timer = timeoutMs > 0 ? setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs) : undefined
  const forwardAbort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  else options.signal?.addEventListener("abort", forwardAbort, { once: true })
  const key = options.apiKey ?? getApiKey()
  const headers: Record<string, string> = { accept: "application/json" }
  if (options.body !== undefined) headers["content-type"] = "application/json"
  if (key) headers["x-api-key"] = key
  try {
    const response = await (options.fetchImpl ?? fetch)(`${options.baseUrl ?? apiBase}${path}`, {
      method: options.method ?? (options.body === undefined ? "GET" : "POST"),
      headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: controller.signal,
    })
    return { response }
  } catch (error) {
    if (timedOut) return { error: new ApiError("timeout", 0, `API did not answer within ${Math.round(timeoutMs / 1000)} s`) }
    if (controller.signal.aborted) return { error: new ApiError("aborted", 0, "request cancelled") }
    return { error: new ApiError("network", 0, `API unreachable (${error instanceof Error ? error.message : "network error"})`) }
  } finally {
    if (timer) clearTimeout(timer)
    options.signal?.removeEventListener("abort", forwardAbort)
  }
}

const failure = <T,>(error: ApiError): ApiResult<T> => ({ ok: false, error, status: error.status, detail: error.detail })

/** JSON request with timeout, cancellation, API key and optional response validation. Never throws. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const sent = await send(path, options)
  if ("error" in sent) return failure(sent.error)
  const { response } = sent
  const data = await response.json().catch(() => null) as unknown
  if (!response.ok) return failure(new ApiError("http", response.status, detailOf(data, response.statusText), data))
  const problem = options.validate?.(data) ?? null
  if (problem) return failure(new ApiError("invalid_response", response.status, `unexpected response from ${path.split("?")[0]}: ${problem}`, data))
  return { ok: true, data: data as T, status: response.status, headers: response.headers }
}

export type FetchOutcome<T> = { ok: true; data: T } | { ok: false; status: number; detail: string; kind?: ApiErrorKind }
export type PostOutcome<T> = FetchOutcome<T>

const outcome = <T,>(result: ApiResult<T>): FetchOutcome<T> => result.ok ? { ok: true, data: result.data } : { ok: false, status: result.status, detail: result.detail, kind: result.error.kind }

export async function fetchJson<T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}): Promise<FetchOutcome<T>> {
  return outcome(await request<T>(path, options))
}

export async function getJson<T>(path: string): Promise<T | null> {
  const result = await request<T>(path)
  return result.ok ? result.data : null
}

export async function postJson<T>(path: string, body: unknown, options: Omit<RequestOptions, "method" | "body"> = {}): Promise<PostOutcome<T>> {
  return outcome(await request<T>(path, { ...options, method: "POST", body }))
}

/** Human-readable error line for a failed outcome. */
export const describeFailure = (result: { status: number; detail: string }): string => result.status ? `${result.status}: ${result.detail}` : result.detail

/** Download an API export as a browser file; returns an error message or null. */
export async function downloadFile(path: string, fallbackName: string, timeoutMs = 120_000): Promise<string | null> {
  const sent = await send(path, { timeoutMs })
  if ("error" in sent) return sent.error.detail
  const { response } = sent
  if (!response.ok) {
    const data = await response.json().catch(() => null) as unknown
    return `${response.status}: ${detailOf(data, response.statusText)}`
  }
  const blob = await response.blob()
  const disposition = response.headers.get("content-disposition") ?? ""
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName
  saveBlob(name, blob)
  return null
}

export function saveBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Local JSON export of data already shown in the Studio (no server round trip). */
export function downloadJson(filename: string, value: unknown): void {
  saveBlob(filename, new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }))
}

/** Show a transient Studio notice (rendered by the shell). */
export function announce(message: string): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("archai:notice", { detail: message }))
}

export function announceUnavailable(message: string): void {
  announce(`UNAVAILABLE — ${message}`)
}
