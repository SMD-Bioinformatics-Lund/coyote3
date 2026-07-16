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
    <section className={cn("surface-panel p-3.5", className)}>
      {(title || description || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2 border-b border-border/70 pb-2">
          <div className="min-w-0">
            {title && <h2 className="text-xs font-black uppercase tracking-wide text-foreground">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
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
    <div className={cn("metric-card p-2.5", className)}>
      <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{title}</p>
      <p className="mt-0.5 text-base font-black leading-tight tracking-tight text-foreground">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  )
}
