import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  type AppNotification,
  type NotificationInput,
  loadNotifications,
  notify,
  saveNotifications,
  subscribeNotifications,
} from "./notification-store"

type NotificationContextValue = {
  notifications: AppNotification[]
  unreadCount: number
  push: (input: NotificationInput) => AppNotification
  markRead: (id: string) => void
  markAllRead: () => void
  remove: (id: string) => void
  clear: () => void
}

const NotificationContext = createContext<NotificationContextValue | null>(null)

const toneMeta = {
  success: { icon: CheckCircle2, className: "border-pass/35 bg-pass/10 text-pass" },
  info: { icon: Info, className: "border-primary/35 bg-primary/10 text-primary" },
  warning: { icon: AlertTriangle, className: "border-warn/35 bg-warn/10 text-warn" },
  error: { icon: XCircle, className: "border-destructive/35 bg-destructive/10 text-destructive" },
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<AppNotification[]>(() => loadNotifications())
  const [visibleToasts, setVisibleToasts] = useState<AppNotification[]>([])

  useEffect(() => {
    saveNotifications(notifications)
  }, [notifications])

  useEffect(() => {
    return subscribeNotifications((notification) => {
      setNotifications((current) => [notification, ...current].slice(0, 200))
      setVisibleToasts((current) => [notification, ...current].slice(0, 4))
      window.setTimeout(() => {
        setVisibleToasts((current) => current.filter((item) => item.id !== notification.id))
      }, notification.tone === "error" ? 8000 : 5000)
    })
  }, [])

  const push = useCallback((input: NotificationInput) => notify(input), [])

  const markRead = useCallback((id: string) => {
    setNotifications((current) =>
      current.map((notification) =>
        notification.id === id ? { ...notification, read: true } : notification
      )
    )
  }, [])

  const markAllRead = useCallback(() => {
    setNotifications((current) => current.map((notification) => ({ ...notification, read: true })))
  }, [])

  const remove = useCallback((id: string) => {
    setNotifications((current) => current.filter((notification) => notification.id !== id))
    setVisibleToasts((current) => current.filter((notification) => notification.id !== id))
  }, [])

  const clear = useCallback(() => {
    setNotifications([])
    setVisibleToasts([])
  }, [])

  const value = useMemo<NotificationContextValue>(
    () => ({
      notifications,
      unreadCount: notifications.filter((notification) => !notification.read).length,
      push,
      markRead,
      markAllRead,
      remove,
      clear,
    }),
    [clear, markAllRead, markRead, notifications, push, remove]
  )

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-20 z-[80] flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2">
        {visibleToasts.map((notification) => (
          <NotificationToast key={notification.id} notification={notification} onClose={() => remove(notification.id)} />
        ))}
      </div>
    </NotificationContext.Provider>
  )
}

function NotificationToast({
  notification,
  onClose,
}: {
  notification: AppNotification
  onClose: () => void
}) {
  const meta = toneMeta[notification.tone]
  const Icon = meta.icon
  const resourceChips = [
    notification.resource?.sampleName ? `Sample ${notification.resource.sampleName}` : "",
    notification.resource?.finding ? `Finding ${notification.resource.finding}` : "",
    notification.resource?.type && (notification.resource.name || notification.resource.id)
      ? `${notification.resource.type}: ${notification.resource.name || notification.resource.id}`
      : "",
  ].filter(Boolean)
  return (
    <div className="pointer-events-auto animate-in slide-in-from-right-3 fade-in rounded-xl border border-border bg-card p-3 shadow-lg">
      <div className="flex items-start gap-3">
        <div className={cn("mt-0.5 rounded-lg border p-1.5", meta.className)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-black text-foreground">{notification.title}</p>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {notification.message && (
            <p className="mt-1 max-h-24 overflow-auto text-xs leading-5 text-muted-foreground">{notification.message}</p>
          )}
          {resourceChips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {resourceChips.map((chip) => (
                <span key={chip} className="rounded-md border border-border bg-background/80 px-1.5 py-0.5 text-[10px] font-bold text-muted-foreground">
                  {chip}
                </span>
              ))}
            </div>
          )}
          {notification.source && (
            <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{notification.source}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error("useNotifications must be used inside NotificationProvider")
  }
  return context
}
