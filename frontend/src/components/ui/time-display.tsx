import type { ReactNode } from "react"
import { Clock3 } from "lucide-react"

import { fullDateTime, humanRelativeDate } from "@/lib/detail-formatters"
import { cn } from "@/lib/utils"

export function TimeDisplay({
  value,
  mode = "relative",
  fallback = "-",
  prefix,
  suffix,
  className,
}: {
  value: unknown
  mode?: "relative" | "full"
  fallback?: string
  prefix?: ReactNode
  suffix?: ReactNode
  className?: string
}) {
  if (value === null || value === undefined || value === "") {
    return <span className={className}>{fallback}</span>
  }

  const absolute = fullDateTime(value, "")
  const visible = mode === "full" ? absolute : humanRelativeDate(value, "")
  if (!visible) return <span className={className}>{fallback}</span>

  return (
    <span
      className={cn("inline-flex items-center gap-1 whitespace-nowrap", className)}
      title={mode === "relative" && absolute ? absolute : undefined}
    >
      <Clock3 className="size-3 shrink-0" aria-hidden="true" />
      {prefix}
      <span>{visible}</span>
      {suffix}
    </span>
  )
}
