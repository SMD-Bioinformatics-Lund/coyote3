import { Bell, CheckCheck, Mail, Trash2, X } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { TimeDisplay } from "@/components/ui/time-display"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { NotificationSeverityBadge } from "@/components/notifications/NotificationSeverityBadge"
import { useNotifications } from "@/components/notifications/use-notifications"
import { cn } from "@/lib/utils"

export function NotificationHistoryPage() {
  const { notifications, unreadCount, markRead, markUnread, markAllRead, remove, clear } = useNotifications()
  return <PageShell eyebrow="Account" title="Notifications" actions={<>
    <Button variant="outline" onClick={markAllRead} disabled={!unreadCount}><CheckCheck className="h-4 w-4" />Mark read</Button>
    <Button variant="outline" onClick={clear} disabled={!notifications.length} title="Clear your tray for this browser session"><Trash2 className="h-4 w-4" />Clear</Button>
  </>}>
    <section className="surface-panel divide-y divide-border px-3">
      {!notifications.length && <div className="flex min-h-48 items-center justify-center gap-3 text-muted-foreground"><Bell className="h-6 w-6" /><p>No notifications yet</p></div>}
      {notifications.map((notification) => <article key={notification.id} className={cn("flex items-start gap-2 py-3", !notification.read && "bg-primary/5")}>
        <details className="min-w-0 flex-1" onToggle={(event) => { if (event.currentTarget.open && !notification.read) markRead(notification.id) }}>
          <summary className="cursor-pointer rounded px-2 py-1 focus-visible:outline-2 focus-visible:outline-ring">
            <span className="ml-1 inline-flex max-w-full flex-wrap items-center gap-2 align-middle"><NotificationSeverityBadge notification={notification} /><span className="min-w-0 break-words text-sm font-semibold [overflow-wrap:anywhere]">{notification.title}</span></span>
          </summary>
          <div className="space-y-3 overflow-auto px-3 py-3">
            {notification.isBroadcast ? <MarkdownText text={notification.message} className="break-words [overflow-wrap:anywhere]" /> : <p className="whitespace-pre-wrap break-words text-sm">{notification.message}</p>}
            {notification.resource?.uri && <a className="link-text" href={notification.resource.uri}>Open details</a>}
            <div className="flex flex-wrap gap-3 type-meta text-muted-foreground"><span>{notification.read ? "Read" : "Unread"}</span><span>{notification.source}</span><TimeDisplay value={notification.createdAt} mode="full" />{notification.expiresAt && <span>Expires <TimeDisplay value={notification.expiresAt} mode="full" /></span>}</div>
          </div>
        </details>
        <div className="flex shrink-0 gap-1">
          {!notification.read && <Button variant="ghost" size="icon-sm" onClick={() => markRead(notification.id)} title="Mark notification as read" aria-label="Mark notification as read"><CheckCheck className="h-4 w-4" /></Button>}
          {notification.read && <Button variant="ghost" size="icon-sm" onClick={() => markUnread(notification.id)} title="Mark notification as unread" aria-label="Mark notification as unread"><Mail className="h-4 w-4" /></Button>}
          <Button variant="ghost" size="icon-sm" onClick={() => remove(notification.id)} title="Remove notification" aria-label="Close notification for this session"><X className="h-4 w-4" /></Button>
        </div>
      </article>)}
    </section>
  </PageShell>
}
