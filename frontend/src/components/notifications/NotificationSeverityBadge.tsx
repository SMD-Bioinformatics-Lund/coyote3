import { cn } from "@/lib/utils"
import type { AppNotification } from "./notification-store"

const severityStyles = {
  info: "bg-primary/10 text-primary border-primary/25",
  important: "bg-accent text-accent-foreground border-border",
  warning: "bg-warn/10 text-warn border-warn/25",
  critical: "bg-destructive/10 text-destructive border-destructive/25",
  success: "bg-pass/10 text-pass border-pass/25",
}

export function NotificationSeverityBadge({ notification }: { notification: Pick<AppNotification, "severity" | "tone"> }) {
  const severity = notification.severity ?? (notification.tone === "error" ? "critical" : notification.tone)
  return <span className={cn("shrink-0 rounded border px-1.5 py-0.5 type-label font-semibold uppercase", severityStyles[severity])}>{severity}</span>
}
