// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Badge } from "@/components/ui/badge"
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { icon } from "@/lib/assets"
import { cn } from "@/lib/utils"
import { apiPath, appPath } from "@/lib/runtime-paths"
import { api, ApiClientError } from "@/lib/api"
import { NotificationSeverityBadge } from "./NotificationSeverityBadge"
import { NOTIFICATION_STORAGE_PREFIX, SESSION_CHANGED_EVENT } from "@/lib/session-state"
import { NotificationContext, type NotificationContextValue } from "./notification-context"
import {
  type AppNotification,
  type NotificationInput,
  notify,
  subscribeNotifications,
} from "./notification-store"

const toneMeta = {
  success: { icon: icon.checkCircle2, className: "border-pass/35 bg-pass/10 text-pass" },
  info: { icon: icon.info, className: "border-primary/35 bg-primary/10 text-primary" },
  warning: { icon: icon.alertTriangle, className: "border-warn/35 bg-warn/10 text-warn" },
  error: { icon: icon.xCircle, className: "border-destructive/35 bg-destructive/10 text-destructive" },
}

function newestFirst(a: AppNotification, b: AppNotification) {
  return Date.parse(b.createdAt) - Date.parse(a.createdAt) || b.id.localeCompare(a.id)
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const sessionGeneration = useRef(0)
  const inboxRequest = useRef(0)
  const historyRequest = useRef(0)
  const newestPage = useRef<AppNotification[]>([])
  const usernameRef = useRef("")
  const [streamUser, setStreamUser] = useState("")
  const initializedServerInbox = useRef(false)
  const seenServerIds = useRef(new Set<string>())
  const hiddenIds = useRef(new Set<string>())
  const sessionKey = () => `${NOTIFICATION_STORAGE_PREFIX}${usernameRef.current}`
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [visibleToasts, setVisibleToasts] = useState<AppNotification[]>([])

  useEffect(() => {
    const reset = () => {
      try { if (usernameRef.current) window.sessionStorage.removeItem(sessionKey()) } catch { /* Storage may be disabled. */ }
      hiddenIds.current.clear()
      sessionGeneration.current += 1
      newestPage.current = []
      usernameRef.current = ""
      setStreamUser("")
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

  const refreshServerInbox = useCallback(async (latestOnly = false) => {
    const generation = sessionGeneration.current
    const request = ++inboxRequest.current
    try {
      const identityResponse = await fetch(apiPath("/auth/whoami"), { credentials: "same-origin" })
      if (generation !== sessionGeneration.current || request !== inboxRequest.current) return
      if (!identityResponse.ok) {
        if (identityResponse.status !== 401 && identityResponse.status !== 403) return
        try { if (usernameRef.current) window.sessionStorage.removeItem(sessionKey()) } catch { /* Storage may be disabled. */ }
        hiddenIds.current.clear()
        newestPage.current = []
        historyRequest.current++
        usernameRef.current = ""
        setStreamUser("")
        setNotifications([])
        setVisibleToasts([])
        initializedServerInbox.current = false
        seenServerIds.current.clear()
        return
      }
      const identity = await identityResponse.json() as { username?: string; must_change_password?: boolean }
      if (generation !== sessionGeneration.current || request !== inboxRequest.current) return
      if (identity.must_change_password) {
        historyRequest.current++
        newestPage.current = []
        setStreamUser("")
        setNotifications([])
        setVisibleToasts([])
        return
      }
      const nextUsername = String(identity.username || "").trim().toLowerCase()
      if (!nextUsername) return
      const changedUser = usernameRef.current !== nextUsername
      if (changedUser) {
        usernameRef.current = nextUsername
        newestPage.current = []
        setStreamUser("")
        setNotifications([])
        setVisibleToasts([])
        initializedServerInbox.current = false
        seenServerIds.current.clear()
        try {
          const saved = JSON.parse(window.sessionStorage.getItem(sessionKey()) || "{}") as { hidden?: unknown; local?: unknown }
          hiddenIds.current = new Set(Array.isArray(saved?.hidden) ? saved.hidden.filter(id => typeof id === "string") : [])
          setNotifications(Array.isArray(saved?.local) ? saved.local.filter((item): item is AppNotification =>
            item !== null && typeof item === "object" && typeof item.id === "string"
              && typeof item.title === "string" && typeof item.createdAt === "string"
              && typeof item.read === "boolean" && Object.hasOwn(toneMeta, item.tone)
              && !item.persisted,
          ) : [])
        } catch { hiddenIds.current.clear() }
      }

      const inboxResponse = await fetch(apiPath("/notifications?limit=200"), {
        credentials: "same-origin",
      })
      if (!inboxResponse.ok) return
      const payload = await inboxResponse.json() as { notifications?: ServerNotification[] }
      const isCurrent = () => generation === sessionGeneration.current && request === inboxRequest.current && usernameRef.current === nextUsername
      if (!isCurrent()) return
      let rows = payload.notifications || []
      const newest = rows.map(mapServerNotification)
      if (initializedServerInbox.current) {
        newest.filter(item => !item.read && !hiddenIds.current.has(item.id) && !seenServerIds.current.has(item.id))
          .slice(0, 4).reverse().forEach(showToast)
      }
      initializedServerInbox.current = true
      newestPage.current = newest
      newest.forEach(item => seenServerIds.current.add(item.id))
      setStreamUser(nextUsername)

      // Keep the newest authorized page visible during history reads, including newer
      // arrivals that displace rows across the page boundary.
      function applySnapshot(head: AppNotification[], history?: AppNotification[]) {
        const boundary = head.at(-1)
        setNotifications(current => {
          const local = current.filter(item => !item.persisted)
          const older = boundary ? (history ?? current.filter(item => item.persisted))
            .filter(item => newestFirst(item, boundary) > 0) : []
          const merged = new Map([...head, ...older, ...local].map(item => [item.id, item]))
          return [...merged.values()].filter(item => !hiddenIds.current.has(item.id)).sort(newestFirst)
        })
      }
      if (rows.length < 200) {
        historyRequest.current++
        applySnapshot(newest, [])
        seenServerIds.current = new Set(newest.map(item => item.id))
        return
      }
      applySnapshot(newest)
      if (latestOnly && !changedUser) return
      const history = ++historyRequest.current
      const historyIsCurrent = () => history === historyRequest.current && generation === sessionGeneration.current && usernameRef.current === nextUsername
      const all = [...newest]
      let offset = rows.length
      while (rows.length === 200) {
        const page = await fetch(apiPath(`/notifications?limit=200&offset=${offset}`), { credentials: "same-origin" })
        if (!page.ok || !historyIsCurrent()) return
        const older = await page.json() as { notifications?: ServerNotification[] }
        if (!historyIsCurrent()) return
        rows = older.notifications || []
        offset += rows.length
        all.push(...rows.map(mapServerNotification))
      }
      applySnapshot(newestPage.current, all)
      seenServerIds.current = new Set([...newestPage.current, ...all].map(item => item.id))
    } catch {
      // A later focus, stream signal or recovery poll retries the inbox read.
    }
  }, [showToast])

  const refreshState = useRef({ running: false, again: false })
  const refresh = useCallback(async () => {
    const state = refreshState.current
    if (state.running) { state.again = true; return }
    state.running = true
    try {
      do {
        state.again = false
        await refreshServerInbox(true)
      } while (state.again)
    } finally {
      state.running = false
    }
  }, [refreshServerInbox])

  useEffect(() => {
    const state = refreshState.current
    const reload = () => void refreshServerInbox()
    reload()
    const interval = window.setInterval(reload, 30_000)
    window.addEventListener("focus", reload)
    window.addEventListener(SESSION_CHANGED_EVENT, reload)
    return () => {
      inboxRequest.current += 1
      historyRequest.current += 1
      state.again = false
      window.clearInterval(interval)
      window.removeEventListener("focus", reload)
      window.removeEventListener(SESSION_CHANGED_EVENT, reload)
    }
  }, [refreshServerInbox])

  useEffect(() => {
    if (!streamUser || typeof EventSource === "undefined") return
    const source = new EventSource(apiPath("/notifications/events"))
    source.addEventListener("ready", refresh)
    source.addEventListener("changed", refresh)
    return () => source.close()
  }, [refresh, streamUser])

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
      setNotifications((current) => [notification, ...current].sort(newestFirst))
      showToast(notification)
    })
  }, [showToast])

  const updateServerState = useCallback(async (path: string, method: "PATCH" | "DELETE") => {
    try {
      if (method === "PATCH") await api.patch(path)
      else await api.delete(path)
      return true
    } catch (error) {
      if (!(error instanceof ApiClientError)) notify({ tone: "error", title: "Notification update failed", message: "Your change was not saved. Please try again." })
      return false
    }
  }, [])

  const push = useCallback((input: NotificationInput) => notify(input), [])

  const markRead = useCallback((id: string) => {
    const persisted = notifications.some((item) => item.id === id && item.persisted)
    const generation = sessionGeneration.current
    void (async () => {
      if (persisted && !await updateServerState(`/notifications/${encodeURIComponent(id)}/read`, "PATCH")) return
      if (generation !== sessionGeneration.current) return
      setNotifications(current => current.map(item => item.id === id ? { ...item, read: true } : item))
    })()
  }, [notifications, updateServerState])

  const markAllRead = useCallback(() => {
    const generation = sessionGeneration.current
    const ids = new Set(notifications.map(item => item.id))
    void (async () => {
      if (notifications.some(item => item.persisted) && !await updateServerState("/notifications/read-all", "PATCH")) return
      if (generation !== sessionGeneration.current) return
      setNotifications(current => current.map(item => ids.has(item.id) ? { ...item, read: true } : item))
    })()
  }, [notifications, updateServerState])

  const markUnread = useCallback((id: string) => {
    const persisted = notifications.some((item) => item.id === id && item.persisted)
    const generation = sessionGeneration.current
    void (async () => {
      if (persisted && !await updateServerState(`/notifications/${encodeURIComponent(id)}/unread`, "PATCH")) return
      if (generation !== sessionGeneration.current) return
      setNotifications(current => current.map(item => item.id === id ? { ...item, read: false } : item))
    })()
  }, [notifications, updateServerState])

  const remove = useCallback((id: string) => {
    const persisted = notifications.some((item) => item.id === id && item.persisted)
    const generation = sessionGeneration.current
    void (async () => {
      if (persisted && !await updateServerState(`/notifications/${encodeURIComponent(id)}/dismiss`, "PATCH")) return
      if (generation !== sessionGeneration.current) return
      hiddenIds.current.add(id)
      setNotifications((current) => current.filter((notification) => notification.id !== id))
      setVisibleToasts((current) => current.filter((notification) => notification.id !== id))
    })()
  }, [notifications, updateServerState])

  const clear = useCallback(() => {
    const generation = sessionGeneration.current
    const ids = new Set(notifications.map((item) => item.id))
    void (async () => {
      if (notifications.some((item) => item.persisted) && !await updateServerState("/notifications", "DELETE")) return
      if (generation !== sessionGeneration.current) return
      for (const id of ids) hiddenIds.current.add(id)
      setNotifications((current) => current.filter((item) => !ids.has(item.id)))
      setVisibleToasts((current) => current.filter((item) => !ids.has(item.id)))
    })()
  }, [notifications, updateServerState])

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
              <icon.x className="h-3.5 w-3.5" />
            </button>
          </div>
          {notification.message && !notification.isBroadcast && (
            <p className="mt-1 max-h-24 overflow-auto text-xs leading-5 text-muted-foreground">{notification.message}</p>
          )}
          {notification.isBroadcast && <a href={appPath("/notifications")} className="link-text text-xs">Open notification</a>}
          {resourceChips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {resourceChips.map((chip) => (
                <Badge variant="outline" key={chip} className="border-border bg-background/80 text-muted-foreground">
                  {chip}
                </Badge>
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
