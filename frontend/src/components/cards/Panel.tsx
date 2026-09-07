import { type ReactNode } from "react"
import { cn } from "@/lib/utils"

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
    <section className={cn("surface-panel p-4 sm:p-5", className)}>
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
    </section>
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
    <div className={cn("metric-card p-4", className)}>
      <p className="type-label text-muted-foreground">{title}</p>
      <p className="mt-1 text-xl font-semibold leading-tight text-foreground">{value}</p>
      {sub && <p className="type-meta mt-1 text-muted-foreground">{sub}</p>}
    </div>
  )
}
