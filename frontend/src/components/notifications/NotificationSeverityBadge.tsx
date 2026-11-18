// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Badge } from "@/components/ui/badge"
import type { AppNotification } from "./notification-store"

const severityStyles = {
  info: "badge-info",
  important: "badge-signal",
  warning: "badge-warning",
  critical: "badge-danger",
  success: "badge-success",
}

export function NotificationSeverityBadge({ notification }: { notification: Pick<AppNotification, "severity" | "tone"> }) {
  const severity = notification.severity ?? (notification.tone === "error" ? "critical" : notification.tone)
  return <Badge variant="outline" className={`uppercase ${severityStyles[severity]}`}>{severity}</Badge>
}
