function normalizePrefix(value?: string) {
  const raw = String(value || "").trim()
  if (!raw || raw === "/") return ""
  return `/${raw.replace(/^\/+|\/+$/g, "")}`
}

const envPrefix = normalizePrefix(runtimeConfig.scriptName)

export const APP_BASENAME = envPrefix

export function appPath(path = "/") {
  const normalized = path.startsWith("/") ? path : `/${path}`
  if (!APP_BASENAME) return normalized
  if (normalized === "/") return APP_BASENAME
  return `${APP_BASENAME}${normalized}`
}

export function apiPath(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`
  return `${APP_BASENAME}/api/v1${normalized}`
}
import { runtimeConfig } from "@/lib/runtime-config"
