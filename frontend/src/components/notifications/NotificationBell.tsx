// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useRef } from "react"
import { Link } from "react-router-dom"
import { TimeDisplay } from "@/components/ui/time-display"
import { icon } from "@/lib/assets"
import { cn } from "@/lib/utils"
import { useNotifications } from "./use-notifications"

export function NotificationBell({ open, onOpenChange }: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { notifications, unreadCount } = useNotifications()
  const trigger = useRef<HTMLButtonElement>(null)
  return (
    <div className="sm:relative" onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) onOpenChange(false)
    }} onKeyDown={event => {
      if (open && event.key === "Escape") {
        onOpenChange(false)
        trigger.current?.focus()
      }
    }}>
      <button ref={trigger} type="button" aria-label="Notifications" aria-expanded={open}
        aria-controls={open ? "recent-notifications" : undefined} onClick={() => onOpenChange(!open)}
        className={cn("relative inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--chrome-border)] bg-[var(--chrome-control)] text-chrome-muted-foreground hover:bg-[var(--chrome-control-hover)] hover:text-chrome-foreground",
          open && "border-[var(--chrome-active-border)] bg-[var(--chrome-active)] text-chrome-foreground")}>
        <icon.bell className="h-5 w-5" />
        {unreadCount > 0 && <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-primary px-1.5 py-0.5 type-label font-semibold leading-none text-primary-foreground">{unreadCount > 99 ? "99+" : unreadCount}</span>}
      </button>
      {open && <section id="recent-notifications" aria-label="Recent notifications"
        className="paper-menu absolute right-0 top-full z-50 mt-2 flex max-h-[70dvh] w-80 max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-lg text-foreground">
        <h2 className="shrink-0 border-b border-border px-4 py-2.5 text-sm font-semibold">Notifications</h2>
        {notifications.length ? <ul className="divide-y divide-border/60 overflow-y-auto overscroll-contain">
          {notifications.slice(0, 5).map(item => <li key={item.id} className="px-4 py-2.5">
            <div className="flex items-baseline gap-2">
              {!item.read && <span className="size-1.5 shrink-0 self-center rounded-full bg-primary"><span className="sr-only">Unread</span></span>}
              <span className={cn("min-w-0 break-words text-sm", !item.read && "font-semibold")}>{item.title}</span>
            </div>
            {item.message && <p className="mt-0.5 line-clamp-2 break-words text-xs text-muted-foreground">{item.message}</p>}
            <TimeDisplay value={item.createdAt} className="mt-1 type-meta text-muted-foreground" />
          </li>)}
        </ul> : <p className="px-4 py-4 text-sm text-muted-foreground">No notifications yet</p>}
        <Link to="/notifications" onClick={() => onOpenChange(false)} className="flex shrink-0 items-center justify-between border-t border-border px-4 py-2.5 text-sm font-semibold text-primary hover:bg-muted">
          Open notification center <icon.chevronRight className="size-4" />
        </Link>
      </section>}
    </div>
  )
}
