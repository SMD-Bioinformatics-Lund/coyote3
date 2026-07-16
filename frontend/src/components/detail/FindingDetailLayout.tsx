import { type ReactNode } from "react"
import { Link } from "react-router-dom"
import { Activity, ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"

export function FindingLoading() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <Activity className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  )
}

export function FindingError({
  title,
  message,
  backTo,
}: {
  title: string
  message: ReactNode
  backTo: string
}) {
  return (
    <div className="p-8 text-destructive">
      <h2 className="mb-4 text-2xl font-bold">{title}</h2>
      <p>{message}</p>
      <Link to={backTo} className="mt-4 inline-flex items-center text-primary hover:underline">
        <ArrowLeft className="mr-2 h-4 w-4" /> Back to Sample
      </Link>
    </div>
  )
}

export function FindingDetailShell({ children }: { children: ReactNode }) {
  return (
    <div className="detail-page">
      <div className="mx-auto w-full max-w-[2600px] flex-1 space-y-3 p-2 lg:p-3">{children}</div>
    </div>
  )
}

export function FindingHero({
  backTo,
  title,
  subtitle,
  chips,
  actions,
  statLabel,
  statValue,
}: {
  backTo: string
  title: ReactNode
  subtitle?: ReactNode
  chips?: ReactNode
  actions?: ReactNode
  statLabel?: ReactNode
  statValue?: ReactNode
}) {
  return (
    <div className="detail-hero">
      <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-start">
        <Link to={backTo} className="soft-icon-button">
          <ArrowLeft className="h-5 w-5" />
        </Link>

        <div className="min-w-0 flex-1">
          <h2 className="flex flex-wrap items-baseline gap-3 text-3xl font-black tracking-tight text-foreground">
            <span className="brand-gradient-text">{title}</span>
          </h2>
          {subtitle && <div className="mt-2 text-muted-foreground">{subtitle}</div>}
          {chips && <div className="mt-3 flex flex-wrap items-center gap-2">{chips}</div>}
        </div>

        {(actions || statValue) && (
          <div className="flex shrink-0 flex-wrap items-start justify-end gap-3 md:ml-auto">
            {actions}
            {statValue && (
              <div className="flex flex-col items-end">
                {statLabel && (
                  <span className="mb-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                    {statLabel}
                  </span>
                )}
                <span className="detail-stat-positive">{statValue}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function FindingMainGrid({
  main,
  aside,
}: {
  main: ReactNode
  aside?: ReactNode
}) {
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_23rem]">
      <div className="min-w-0 space-y-3">{main}</div>
      {aside && <aside className="min-w-0 space-y-3">{aside}</aside>}
    </div>
  )
}

export function DetailCard({
  title,
  children,
  tone = "accent",
  className,
}: {
  title: ReactNode
  children: ReactNode
  tone?: "accent" | "success" | "info"
  className?: string
}) {
  const toneClass = {
    accent: "detail-card-accent",
    success: "detail-card-success",
    info: "detail-card-info",
  }[tone]

  return (
    <div className={cn(toneClass, className)}>
      <h3 className="detail-section-title">{title}</h3>
      {children}
    </div>
  )
}

export function DetailField({
  label,
  children,
  valueClassName,
}: {
  label: ReactNode
  children: ReactNode
  valueClassName?: string
}) {
  return (
    <div className="min-w-0">
      <span className="detail-field-label">{label}</span>
      <div className={cn("detail-field-value", valueClassName)}>{children}</div>
    </div>
  )
}

export function DetailFieldGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">{children}</div>
}
