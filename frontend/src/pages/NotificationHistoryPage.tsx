import { Bell, CheckCheck, Trash2 } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { useNotifications } from "@/components/notifications/use-notifications"
import { cn } from "@/lib/utils"

const toneClass = {
  success: "border-pass bg-pass/10 text-pass",
  info: "border-primary bg-primary/10 text-primary",
  warning: "border-warn bg-warn/10 text-warn",
  error: "border-destructive bg-destructive/10 text-destructive",
}

export function NotificationHistoryPage() {
  const { notifications, unreadCount, markAllRead, remove, clear } = useNotifications()

  return (
    <PageShell
      eyebrow="Account"
      title="Notifications"
      description="Recent application messages, API failures, and workflow feedback retained locally in this browser."
      actions={
        <>
          <Button variant="outline" onClick={markAllRead} disabled={!unreadCount}>
            <CheckCheck className="h-4 w-4" />
            Mark read
          </Button>
          <Button variant="destructive" onClick={clear} disabled={!notifications.length}>
            <Trash2 className="h-4 w-4" />
            Clear
          </Button>
        </>
      }
    >
      <section className="surface-panel p-3">
        {!notifications.length ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
            <div className="rounded-xl border border-border bg-muted/40 p-3">
              <Bell className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-foreground">No notifications yet</p>
              <p className="mt-1 text-sm">Application and API messages will appear here.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {notifications.map((notification) => (
              <article
                key={notification.id}
                className={cn(
                  "rounded-xl border border-border bg-card/80 p-3 shadow-sm transition-colors",
                  !notification.read && "border-primary/40 bg-primary/5"
                )}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-black uppercase", toneClass[notification.tone])}>
                        {notification.tone}
                      </span>
                      {notification.source && (
                        <span className="truncate text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
                          {notification.source}
                        </span>
                      )}
                    </div>
                    <h2 className="mt-2 text-sm font-black text-foreground">{notification.title}</h2>
                    {notification.message && (
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{notification.message}</p>
                    )}
                    <p className="mt-2 text-[11px] font-medium text-muted-foreground">
                      {new Date(notification.createdAt).toLocaleString()}
                    </p>
                  </div>
                  <Button variant="ghost" size="icon-sm" onClick={() => remove(notification.id)} title="Remove notification">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </PageShell>
  )
}
