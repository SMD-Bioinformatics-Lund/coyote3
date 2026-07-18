function normalizePrefix(value?: string) {
  const raw = String(value || "").trim()
  if (!raw || raw === "/") return ""
  return `/${raw.replace(/^\/+|\/+$/g, "")}`
}

const envPrefix = normalizePrefix(import.meta.env.VITE_SCRIPT_NAME)

export const APP_BASENAME = envPrefix

export function normalizeMountedRootUrl() {
  if (!APP_BASENAME || typeof window === "undefined") return
  if (window.location.pathname !== APP_BASENAME) return
  window.history.replaceState(
    window.history.state,
    "",
    `${APP_BASENAME}/${window.location.search}${window.location.hash}`,
  )
}

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
