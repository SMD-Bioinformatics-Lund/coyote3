import { notify } from "@/components/notifications/notification-store"
import type { NotificationResource } from "@/components/notifications/notification-store"
import { ApiClientError } from "@/lib/api"

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === "string" && error.trim()) return error
  return fallback
}

export function notifySuccess(title: string, message?: string, source?: string, resource?: NotificationResource) {
  notify({ tone: "success", title, message, source, resource })
}

export function notifyWarning(title: string, message?: string, source?: string, resource?: NotificationResource) {
  notify({ tone: "warning", title, message, source, resource })
}

export function notifyActionError(title: string, error: unknown, source?: string, resource?: NotificationResource) {
  if (error instanceof ApiClientError && error.notificationShown) return
  notify({
    tone: "error",
    title,
    message: errorMessage(error, "The action could not be completed."),
    source,
    resource,
  })
}
