// A lightweight typed wrapper around native fetch.

import { notify } from "@/components/notifications/notification-store"
import { apiPath, appPath } from "@/lib/runtime-paths"

export class ApiClientError extends Error {
  notificationShown = true
  status?: number
  endpoint?: string
  code?: string
  requestId?: string
  retryAfter?: string

  constructor(message: string, status?: number, endpoint?: string) {
    super(message)
    this.name = "ApiClientError"
    this.status = status
    this.endpoint = endpoint
  }
}

export type ApiResponse<T> = {
  data: T
  status: number
}

type ApiBody = BodyInit | Record<string, unknown> | unknown[] | null | undefined

let csrfToken: string | null = null

export function setCsrfToken(token: string | null | undefined) {
  csrfToken = token || null
}

let errorReportWindow = 0
let errorReportCount = 0

export function reportUiError(error: unknown, componentStack = "") {
  if (!csrfToken) return
  const now = Date.now()
  if (now - errorReportWindow > 60000) {
    errorReportWindow = now
    errorReportCount = 0
  }
  if (errorReportCount >= 10) return
  errorReportCount += 1
  const message = error instanceof Error ? error.message : String(error || "Unknown UI error")
  const stack = error instanceof Error ? error.stack || "" : ""
  // Reporting failures must never trigger another report or replace the original UI error.
  void fetch(apiPath("/client-errors"), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ message: message.slice(0, 4000), stack: `${stack}\n${componentStack}`.slice(0, 16000) }),
    keepalive: true,
  }).catch(() => undefined)
}

function encodeBody(body: ApiBody): BodyInit | undefined {
  if (body === undefined || body === null) return undefined
  if (body instanceof FormData || body instanceof Blob || typeof body === "string") return body
  return JSON.stringify(body)
}

async function request<T = any>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
  const url = apiPath(endpoint)
  const isFormData = options.body instanceof FormData
  const method = (options.method ?? "GET").toUpperCase()
  const headers = new Headers(options.headers)
  if (!isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", csrfToken)
  }

  let response: Response
  try {
    response = await fetch(url, { ...options, headers })
  } catch (error) {
    if (recordValue(error).name === "AbortError" || options.signal?.aborted) throw error
    const message = "Could not reach Coyote3. Check your connection and whether the operation completed before retrying."
    notify({ tone: "error", title: "Connection interrupted", message, source: `${method} ${endpoint}` })
    const failure = new ApiClientError(message, 0, endpoint)
    failure.code = "network_error"
    throw failure
  }

  // Global 401 interceptor
  if (response.status === 401 && window.location.pathname !== appPath("/login")) {
    setCsrfToken(null)
    window.location.href = appPath("/login")
    throw new Error("Unauthorized")
  }

  // Handle empty responses
  const text = await response.text()
  const data = text ? safeJson(text) : {}

  if (!response.ok) {
    if (response.status === 403 && (data?.category || data?.detail?.category) === "password_change_required") {
      if (window.location.pathname !== appPath("/profile")) window.location.href = appPath("/profile")
      throw new ApiClientError("Change your temporary password before continuing.", 403, endpoint)
    }
    const requestId = response.headers.get("X-Request-ID") || stringValue(data?.request_id)
    const retryAfter = response.headers.get("Retry-After") || undefined
    const errorMessage = [
      userFacingApiError(response.status, data),
      retryAfter ? `Retry after: ${retryAfter}${/^\d+$/.test(retryAfter) ? " seconds" : ""}.` : "",
      requestId ? `Reference: ${requestId}` : "",
    ].filter(Boolean).join(" ")
    notify({
      tone: response.status >= 500 ? "error" : "warning",
      title: response.status >= 500 ? "System action failed" : "Request could not be completed",
      message: errorMessage,
      source: `${options.method ?? "GET"} ${endpoint}`,
    })
    const failure = new ApiClientError(errorMessage, response.status, endpoint)
    failure.code = stringValue(data?.code)
    failure.requestId = requestId
    failure.retryAfter = retryAfter
    throw failure
  }

  if (
    (endpoint === "/auth/sessions" || endpoint === "/auth/session" || endpoint === "/auth/whoami")
    && data?.csrf_token
  ) {
    setCsrfToken(data.csrf_token)
  }
  if (endpoint === "/auth/sessions/current" && method === "DELETE") setCsrfToken(null)
  return { data: data as T, status: response.status }
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined
}

function recordValue(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {}
}

function userFacingApiError(status: number, value: unknown) {
  if (status >= 500) {
    const titles: Record<number, string> = {
      502: "A dependent service failed.",
      503: "Coyote3 is temporarily unavailable.",
      504: "A dependent service timed out.",
    }
    return `${titles[status] || "The server could not complete the request."} Check whether the operation completed before retrying. Contact support with the reference ID when available.`
  }
  const data = recordValue(value)
  const nested = recordValue(data.detail)
  const fallback: Record<number, string> = {
    400: "The request could not be accepted. Check the supplied values.",
    401: "Authentication is required. Sign in again.",
    403: "Access was denied. Check your permissions or refresh the page before trying again.",
    404: "The requested resource was not found. Refresh the list or check the address.",
    405: "This action is not supported at this address.",
    406: "The requested response format is not supported.",
    408: "The request timed out. Check whether the operation completed before retrying.",
    409: "The change conflicts with the current record. Reload and review before retrying.",
    410: "This resource is no longer available.",
    412: "The record has changed. Reload the current version before retrying.",
    413: "The upload is too large. Reduce its size or contact an administrator about the upload limit.",
    415: "This file or request format is not supported.",
    422: "Validation failed. Check the required fields and their formats.",
    428: "This action requires a record version or precondition.",
    429: "Too many requests. Wait before trying again.",
  }
  const rawError = stringValue(data.error) || stringValue(data.message) || stringValue(nested.error)
    || stringValue(data.detail) || fallback[status] || `Request failed (HTTP ${status})`
  const structured = data.details || nested.details || nested.message || (Array.isArray(data.detail) ? data.detail : null)
  const issues = Array.isArray(structured) ? structured : recordValue(structured).issues
  const details = Array.isArray(issues)
    ? issues.map((value: unknown) => {
        const item = recordValue(value)
        const location = item.loc || item.location
        const field = stringValue(item.field) || (Array.isArray(location) ? location.join(".") : "")
        return [field, stringValue(item.msg) || stringValue(item.message)].filter(Boolean).join(": ")
      }).join("; ")
    : typeof structured === "string" ? structured : ""
  const hint = stringValue(data.hint) || stringValue(nested.hint)
  return [[rawError, details].filter(Boolean).join(": "), hint].filter(Boolean).join(" ")
}

function safeJson(text: string) {
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

export const api = {
  get: <T = any>(url: string, options?: RequestInit) =>
    request<T>(url, { ...options, method: "GET" }),
  post: <T = any>(url: string, body?: ApiBody, options?: RequestInit) =>
    request<T>(url, { ...options, method: "POST", body: encodeBody(body) }),
  patch: <T = any>(url: string, body?: ApiBody, options?: RequestInit) =>
    request<T>(url, { ...options, method: "PATCH", body: encodeBody(body) }),
  put: <T = any>(url: string, body?: ApiBody, options?: RequestInit) =>
    request<T>(url, { ...options, method: "PUT", body: encodeBody(body) }),
  delete: <T = any>(url: string, options?: RequestInit) =>
    request<T>(url, { ...options, method: "DELETE" }),
}
