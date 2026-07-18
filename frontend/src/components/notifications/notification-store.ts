export type NotificationTone = "success" | "info" | "warning" | "error"

export type AppNotification = {
  id: string
  tone: NotificationTone
  title: string
  message?: string
  source?: string
  resource?: NotificationResource
  createdAt: string
  read: boolean
}

export type NotificationResource = {
  type?: string
  id?: string
  name?: string
  sampleName?: string
  finding?: string
}

export type NotificationInput = {
  tone?: NotificationTone
  title: string
  message?: string
  source?: string
  resource?: NotificationResource
}

const STORAGE_KEY = "coyote3.notifications"
const listeners = new Set<(notification: AppNotification) => void>()
const recentNotificationKeys = new Map<string, number>()
const DEDUPE_WINDOW_MS = 10_000

function createId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function createNotification(input: NotificationInput): AppNotification {
  return {
    id: createId(),
    tone: input.tone ?? "info",
    title: input.title,
    message: input.message,
    source: input.source,
    resource: input.resource,
    createdAt: new Date().toISOString(),
    read: false,
  }
}

export function loadNotifications(): AppNotification[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveNotifications(notifications: AppNotification[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications.slice(0, 200)))
}

export function notify(input: NotificationInput) {
  const fingerprint = [
    input.tone ?? "info",
    input.title,
    input.message ?? "",
    input.source ?? "",
    input.resource?.type ?? "",
    input.resource?.id ?? input.resource?.name ?? "",
  ].join("|")
  const now = Date.now()
  const previous = recentNotificationKeys.get(fingerprint)
  if (previous && now - previous < DEDUPE_WINDOW_MS) {
    return null
  }
  recentNotificationKeys.set(fingerprint, now)
  for (const [key, timestamp] of recentNotificationKeys.entries()) {
    if (now - timestamp > DEDUPE_WINDOW_MS) recentNotificationKeys.delete(key)
  }
  const notification = createNotification(input)
  for (const listener of listeners) {
    listener(notification)
  }
  return notification
}

export function subscribeNotifications(listener: (notification: AppNotification) => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
