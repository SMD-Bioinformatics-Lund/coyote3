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
