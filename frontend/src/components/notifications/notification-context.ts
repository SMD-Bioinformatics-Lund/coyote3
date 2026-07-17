import { createContext } from "react"
import type { AppNotification, NotificationInput } from "./notification-store"

export type NotificationContextValue = {
  notifications: AppNotification[]
  unreadCount: number
  push: (input: NotificationInput) => AppNotification
  markRead: (id: string) => void
  markAllRead: () => void
  remove: (id: string) => void
  clear: () => void
}

export const NotificationContext = createContext<NotificationContextValue | null>(null)
