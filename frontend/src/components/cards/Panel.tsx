// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { type ReactNode } from "react"
import { cn } from "@/lib/utils"
import { Surface } from "@/components/ui/surface"

export function SurfacePanel({
  title,
  description,
  actions,
  className,
  children,
}: {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Surface as="section" variant="panel" className={cn("responsive-card-padding", className)}>
      {(title || description || actions) && (
        <div className="surface-panel-heading flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 className="type-card-title text-foreground">{title}</h2>
            )}
            {description && <p className="type-body-sm mt-1 text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </Surface>
  )
}

export function MetricCard({
  title,
  value,
  sub,
  className,
}: {
  title: ReactNode
  value: ReactNode
  sub?: ReactNode
  className?: string
}) {
  return (
    <Surface className={cn("metric-card p-3", className)}>
      <p className="type-label text-muted-foreground">{title}</p>
      <p className="mt-1 type-metric-value text-foreground">{value}</p>
      {sub && <p className="type-meta mt-1 text-muted-foreground">{sub}</p>}
    </Surface>
  )
}
