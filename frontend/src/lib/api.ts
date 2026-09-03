// A lightweight typed wrapper around native fetch.

import { notify } from "@/components/notifications/notification-store"
import { apiPath, appPath } from "@/lib/runtime-paths"

export class ApiClientError extends Error {
  notificationShown = true
  status?: number
  endpoint?: string

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

  const response = await fetch(url, { ...options, headers })

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
    const errorMessage = userFacingApiError(response.status, data, response.statusText)
    notify({
      tone: response.status >= 500 ? "error" : "warning",
      title: response.status >= 500 ? "System action failed" : "Request could not be completed",
      message: errorMessage,
      source: `${options.method ?? "GET"} ${endpoint}`,
    })
    throw new ApiClientError(errorMessage, response.status, endpoint)
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

function userFacingApiError(status: number, data: any, statusText: string) {
  const rawError = data?.error || data?.message || data?.detail?.error || statusText || "Request failed"
  const details = data?.details || data?.detail?.details || data?.detail?.message
  if (status === 403) {
    return "You do not have permission to perform this action. Contact an administrator if this access is expected."
  }
  if (status === 404) {
    return String(rawError || "The requested record was not found.")
  }
  if (status === 409) {
    return String(rawError || "This change conflicts with an existing record.")
  }
  if (status === 422) {
    return [rawError, details].filter(Boolean).join(": ")
  }
  if (status >= 500) {
    return details
      ? `The server could not complete the request: ${details}`
      : `The server could not complete the request. ${rawError}`
  }
  return [rawError, details].filter(Boolean).join(": ")
}

function safeJson(text: string) {
  try {
    return JSON.parse(text)
  } catch {
    return { message: text }
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
