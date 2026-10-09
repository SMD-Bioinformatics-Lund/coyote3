import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { apiPath, appPath } from "@/lib/runtime-paths"
import { api } from "@/lib/api"
import { NotificationSeverityBadge } from "./NotificationSeverityBadge"
import { SESSION_CHANGED_EVENT } from "@/lib/session-state"
import { NotificationContext, type NotificationContextValue } from "./notification-context"
import {
  type AppNotification,
  type NotificationInput,
  notify,
  subscribeNotifications,
} from "./notification-store"

const toneMeta = {
  success: { icon: CheckCircle2, className: "border-pass/35 bg-pass/10 text-pass" },
  info: { icon: Info, className: "border-primary/35 bg-primary/10 text-primary" },
  warning: { icon: AlertTriangle, className: "border-warn/35 bg-warn/10 text-warn" },
  error: { icon: XCircle, className: "border-destructive/35 bg-destructive/10 text-destructive" },
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const sessionGeneration = useRef(0)
  const usernameRef = useRef("")
  const initializedServerInbox = useRef(false)
  const seenServerIds = useRef(new Set<string>())
  const hiddenIds = useRef(new Set<string>())
  const sessionKey = () => `coyote3:notification-tray:${usernameRef.current}`
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [visibleToasts, setVisibleToasts] = useState<AppNotification[]>([])

  useEffect(() => {
    const reset = () => {
      try { if (usernameRef.current) window.sessionStorage.removeItem(sessionKey()) } catch { /* Storage may be disabled. */ }
      hiddenIds.current.clear()
      sessionGeneration.current += 1
      usernameRef.current = ""
      setNotifications([])
      setVisibleToasts([])
      initializedServerInbox.current = false
      seenServerIds.current.clear()
    }
    window.addEventListener(SESSION_CHANGED_EVENT, reset)
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, reset)
  }, [])

  const showToast = useCallback((notification: AppNotification) => {
    setVisibleToasts((current) => [notification, ...current].slice(0, 4))
    window.setTimeout(() => {
      setVisibleToasts((current) => current.filter((item) => item.id !== notification.id))
    }, notification.tone === "error" ? 8000 : 5000)
  }, [])

  const refreshServerInbox = useCallback(async () => {
    const generation = sessionGeneration.current
    try {
      const identityResponse = await fetch(apiPath("/auth/whoami"), { credentials: "same-origin" })
      if (generation !== sessionGeneration.current) return
      if (!identityResponse.ok) {
        try { if (usernameRef.current) window.sessionStorage.removeItem(sessionKey()) } catch { /* Storage may be disabled. */ }
        hiddenIds.current.clear()
        usernameRef.current = ""
        setNotifications([])
        setVisibleToasts([])
        initializedServerInbox.current = false
        seenServerIds.current.clear()
        return
      }
      const identity = await identityResponse.json() as { username?: string; must_change_password?: boolean }
      if (generation !== sessionGeneration.current) return
      if (identity.must_change_password) { setNotifications([]); setVisibleToasts([]); return }
      const nextUsername = String(identity.username || "").trim().toLowerCase()
      if (!nextUsername) return
      const changedUser = usernameRef.current !== nextUsername
      if (changedUser) {
        usernameRef.current = nextUsername
        setNotifications([])
        setVisibleToasts([])
        initializedServerInbox.current = false
        seenServerIds.current.clear()
        try {
          const saved = JSON.parse(window.sessionStorage.getItem(sessionKey()) || "{}") as { hidden?: string[]; local?: AppNotification[] }
          hiddenIds.current = new Set(saved.hidden || [])
          setNotifications(saved.local || [])
        } catch { hiddenIds.current.clear() }
      }

      const inboxResponse = await fetch(apiPath("/notifications?limit=200"), {
        credentials: "same-origin",
      })
      if (!inboxResponse.ok) return
      const payload = await inboxResponse.json() as { notifications?: ServerNotification[] }
      let pageSize = payload.notifications?.length || 0
      let offset = pageSize
      while (pageSize === 200) {
        const page = await fetch(apiPath(`/notifications?limit=200&offset=${offset}`), { credentials: "same-origin" })
        if (!page.ok || generation !== sessionGeneration.current) return
        const older = await page.json() as { notifications?: ServerNotification[] }
        pageSize = older.notifications?.length || 0
        offset += pageSize
        payload.notifications = [...(payload.notifications || []), ...(older.notifications || [])]
      }
      if (generation !== sessionGeneration.current || usernameRef.current !== nextUsername) return
      const serverNotifications = [...new Map((payload.notifications || []).map((item) => [item.id, item])).values()].map(mapServerNotification)
        .filter((item) => !hiddenIds.current.has(item.id))

      if (initializedServerInbox.current) {
        serverNotifications
          .filter((item) => !item.read && !seenServerIds.current.has(item.id))
          .slice(0, 4)
          .forEach(showToast)
      }
      seenServerIds.current = new Set(serverNotifications.map((item) => item.id))
      initializedServerInbox.current = true
      setNotifications((current) => {
        const local = current.filter((item) => !item.persisted)
        return [...serverNotifications, ...local]
          .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
      })
    } catch {
      // Notification polling must never interrupt the active clinical workflow.
    }
  }, [showToast])

  useEffect(() => {
    void refreshServerInbox()
    const interval = window.setInterval(() => void refreshServerInbox(), 30_000)
    const refresh = () => void refreshServerInbox()
    window.addEventListener("focus", refresh)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener("focus", refresh)
    }
  }, [refreshServerInbox])

  useEffect(() => {
    if (!usernameRef.current) return
    try {
      window.sessionStorage.setItem(sessionKey(), JSON.stringify({
        hidden: [...hiddenIds.current], local: notifications.filter((item) => !item.persisted),
      }))
    } catch { /* The current tab remains usable when browser storage is unavailable. */ }
  }, [notifications])

  useEffect(() => {
    return subscribeNotifications((notification) => {
      setNotifications((current) => [notification, ...current])
      showToast(notification)
    })
  }, [showToast])

  const updateServerState = useCallback(async (path: string, method: "PATCH" | "DELETE") => {
    try {
      if (method === "PATCH") await api.patch(path)
      else await api.delete(path)
    } catch {
      // The next inbox refresh reconciles state after a transient network error.
    }
  }, [])

  const push = useCallback((input: NotificationInput) => notify(input), [])

  const markRead = useCallback((id: string) => {
    const persisted = notifications.some((item) => item.id === id && item.persisted)
    setNotifications((current) =>
      current.map((notification) =>
        notification.id === id ? { ...notification, read: true } : notification
      )
    )
    if (persisted) void updateServerState(`/notifications/${encodeURIComponent(id)}/read`, "PATCH")
  }, [notifications, updateServerState])

  const markAllRead = useCallback(() => {
    setNotifications((current) => current.map((notification) => ({ ...notification, read: true })))
    if (notifications.some((item) => item.persisted)) {
      void updateServerState("/notifications/read-all", "PATCH")
    }
  }, [notifications, updateServerState])

  const markUnread = useCallback((id: string) => {
    const persisted = notifications.some((item) => item.id === id && item.persisted)
    setNotifications((current) => current.map((item) => item.id === id ? { ...item, read: false } : item))
    if (persisted) void updateServerState(`/notifications/${encodeURIComponent(id)}/unread`, "PATCH")
  }, [notifications, updateServerState])

  const remove = useCallback((id: string) => {
    hiddenIds.current.add(id)
    setNotifications((current) => current.filter((notification) => notification.id !== id))
    setVisibleToasts((current) => current.filter((notification) => notification.id !== id))
  }, [])

  const clear = useCallback(() => {
    for (const item of notifications) hiddenIds.current.add(item.id)
    setNotifications([])
    setVisibleToasts([])
  }, [notifications])

  const value = useMemo<NotificationContextValue>(
    () => ({
      notifications,
      unreadCount: notifications.filter((notification) => !notification.read).length,
      push,
      markRead,
      markUnread,
      markAllRead,
      remove,
      clear,
    }),
    [clear, markAllRead, markRead, markUnread, notifications, push, remove]
  )

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-20 z-[80] flex w-[min(420px,calc(100vw-2rem))] flex-col gap-2">
        {visibleToasts.map((notification) => (
          <NotificationToast key={notification.id} notification={notification} onClose={() => {
            markRead(notification.id)
            setVisibleToasts((current) => current.filter((item) => item.id !== notification.id))
          }} />
        ))}
      </div>
    </NotificationContext.Provider>
  )
}

type ServerNotification = {
  id: string
  tone: AppNotification["tone"]
  category?: AppNotification["category"]
  title: string
  message?: string
  source?: string
  resource?: {
    type?: string
    id?: string
    name?: string
    sample_name?: string
    finding?: string
    uri?: string
  }
  created_at: string
  read: boolean
  severity?: AppNotification["severity"]
  is_broadcast?: boolean
  can_clear?: boolean
  expires_at?: string | null
  withdrawn_at?: string | null
}

function mapServerNotification(item: ServerNotification): AppNotification {
  return {
    id: item.id,
    tone: item.tone,
    category: item.category,
    title: item.title,
    message: item.message,
    source: item.source,
    resource: item.resource ? {
      type: item.resource.type,
      id: item.resource.id,
      name: item.resource.name,
      sampleName: item.resource.sample_name,
      finding: item.resource.finding,
      uri: item.resource.uri,
    } : undefined,
    createdAt: item.created_at,
    read: item.read,
    persisted: true,
    severity: item.severity,
    isBroadcast: item.is_broadcast,
    canClear: item.can_clear,
    expiresAt: item.expires_at,
    withdrawnAt: item.withdrawn_at,
  }
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
            <p className="text-sm font-semibold text-foreground">{notification.title}</p>
            {notification.isBroadcast && <NotificationSeverityBadge notification={notification} />}
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {notification.message && !notification.isBroadcast && (
            <p className="mt-1 max-h-24 overflow-auto text-xs leading-5 text-muted-foreground">{notification.message}</p>
          )}
          {notification.isBroadcast && <a href={appPath("/notifications")} className="link-text text-xs">Open notification</a>}
          {resourceChips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {resourceChips.map((chip) => (
                <span key={chip} className="rounded-md border border-border bg-background/80 px-1.5 py-0.5 type-label font-semibold text-muted-foreground">
                  {chip}
                </span>
              ))}
            </div>
          )}
          {notification.resource?.uri && (
            <a className="link-text mt-2 inline-flex text-xs font-semibold" href={notification.resource.uri}>
              Open rule set
            </a>
          )}
          {notification.source && (
            <p className="mt-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">{notification.source}</p>
          )}
        </div>
      </div>
    </div>
  )
}
