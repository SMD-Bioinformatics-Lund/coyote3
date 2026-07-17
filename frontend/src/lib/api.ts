// A lightweight typed wrapper around native fetch.
// It intentionally keeps a small `{ data, status }` response object so existing
// React Query call sites can migrate incrementally without adding Axios.

import { notify } from "@/components/notifications/notification-store"

const BASE_URL = "/api/v1"

export class ApiClientError extends Error {
  notificationShown = true
}

export type ApiSuccessEnvelope<T> = {
  status?: "ok" | string
  payload?: T
  meta?: Record<string, unknown>
}

export type ApiListEnvelope<T> = {
  status?: "ok" | string
  items?: T[]
  pagination?: Record<string, unknown>
  meta?: Record<string, unknown>
}

export type ApiResponse<T> = {
  data: T
  status: number
}

type ApiBody = BodyInit | Record<string, unknown> | unknown[] | null | undefined

export function responsePayload<T>(data: ApiSuccessEnvelope<T> | T): T {
  if (data && typeof data === "object" && "payload" in data) {
    return (data as ApiSuccessEnvelope<T>).payload as T
  }
  return data as T
}

export function responseItems<T>(data: ApiListEnvelope<T> | T[]): T[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === "object" && "items" in data) {
    return ((data as ApiListEnvelope<T>).items || []) as T[]
  }
  return []
}

export function unwrapPayload<T>(response: ApiResponse<ApiSuccessEnvelope<T> | T>): T {
  return responsePayload<T>(response.data)
}

export function unwrapItems<T>(response: ApiResponse<ApiListEnvelope<T> | T[]>): T[] {
  return responseItems<T>(response.data)
}

function encodeBody(body: ApiBody): BodyInit | undefined {
  if (body === undefined || body === null) return undefined
  if (body instanceof FormData || body instanceof Blob || typeof body === "string") return body
  return JSON.stringify(body)
}

async function request<T = any>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
  const url = `${BASE_URL}${endpoint}`
  const isFormData = options.body instanceof FormData
  const headers = isFormData
    ? { ...options.headers }
    : {
        "Content-Type": "application/json",
        ...options.headers,
      }

  const response = await fetch(url, { ...options, headers })

  // Global 401 interceptor
  if (response.status === 401 && window.location.pathname !== "/login") {
    window.location.href = "/login"
    throw new Error("Unauthorized")
  }

  // Handle empty responses
  const text = await response.text()
  const data = text ? safeJson(text) : {}

  if (!response.ok) {
    const message = data?.error || data?.message || response.statusText || "Request failed"
    const details = typeof data?.details === "string" ? `: ${data.details}` : ""
    const errorMessage = `API Error: ${response.status} ${message}${details}`
    notify({
      tone: response.status >= 500 ? "error" : "warning",
      title: "API request failed",
      message: errorMessage,
      source: `${options.method ?? "GET"} ${endpoint}`,
    })
    throw new ApiClientError(errorMessage)
  }

  return { data: data as T, status: response.status }
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
  getPayload: async <T = any>(url: string, options?: RequestInit) =>
    unwrapPayload<T>(await request<ApiSuccessEnvelope<T> | T>(url, { ...options, method: "GET" })),
  getItems: async <T = any>(url: string, options?: RequestInit) =>
    unwrapItems<T>(await request<ApiListEnvelope<T> | T[]>(url, { ...options, method: "GET" })),
}
