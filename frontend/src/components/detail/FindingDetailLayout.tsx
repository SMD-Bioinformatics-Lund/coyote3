import { type ReactNode } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, Fingerprint } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { cn } from "@/lib/utils"

export function FindingLoading() {
  return <AppLoader label="Loading finding" />
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
      <Link to={backTo} className="link-text mt-4 inline-flex items-center">
        <ArrowLeft className="mr-2 h-4 w-4" /> Back to Sample
      </Link>
    </div>
  )
}

export function FindingDetailShell({ children }: { children: ReactNode }) {
  return (
    <div className="detail-page">
      <div className="w-full max-w-[2600px] flex-1 space-y-3 p-2 lg:p-3">{children}</div>
    </div>
  )
}

export function DetailHero({
  backTo,
  title,
  subtitle,
  chips,
  actions,
  statLabel,
  statValue,
  density = "default",
}: {
  backTo: string
  title: ReactNode
  subtitle?: ReactNode
  chips?: ReactNode
  actions?: ReactNode
  statLabel?: ReactNode
  statValue?: ReactNode
  density?: "default" | "compact"
}) {
  return (
    <div className="detail-hero">
      <div
        className={cn(
          "detail-hero-row relative z-10 flex h-full flex-col gap-4 md:flex-row md:items-stretch",
          density === "default" && "md:min-h-[9rem]",
        )}
      >
        <Link to={backTo} className="soft-icon-button">
          <ArrowLeft className="h-5 w-5" />
        </Link>

        <div className="min-w-0 flex-1">
          <h2 className="flex flex-wrap items-baseline gap-3 text-3xl font-black tracking-tight text-foreground">
            <span className="brand-gradient-text">{title}</span>
          </h2>
          {subtitle && <div className="mt-2 text-muted-foreground">{subtitle}</div>}
          {chips && <div className="detail-hero-callers mt-3 flex flex-wrap items-center gap-2">{chips}</div>}
        </div>

        {(actions || statValue) && (
          <div className="flex shrink-0 flex-col items-start gap-3 md:ml-auto md:items-end">
            {statValue ? (
              <div className="flex flex-col items-start md:items-end">
                {statLabel && (
                  <span className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {statLabel}
                  </span>
                )}
                <span className="detail-stat-positive">{statValue}</span>
              </div>
            ) : (
              <span className="hidden md:block" aria-hidden="true" />
            )}
            {actions && <div className="mt-auto flex flex-wrap items-center justify-start gap-2 md:justify-end">{actions}</div>}
          </div>
        )}
      </div>
    </div>
  )
}

export function DetailHeroSubtitle({
  children,
  sampleHref,
  sampleName,
}: {
  children: ReactNode
  sampleHref: string
  sampleName: ReactNode
}) {
  return (
    <div className="space-y-2">
      <div className="detail-hero-subtitle">{children}</div>
      <Link to={sampleHref} className="detail-hero-sample-chip">
        Sample {sampleName}
      </Link>
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
  return <div className="detail-field-grid grid grid-cols-1 gap-3 px-2 text-sm sm:grid-cols-2">{children}</div>
}

export function FindingIdentityCard({
  title,
  children,
  className,
}: {
  title: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <DetailCard
      title={(
        <span className="inline-flex items-center gap-2">
          <span className="detail-identity-icon" aria-hidden="true">
            <Fingerprint className="h-4 w-4" />
          </span>
          {title}
        </span>
      )}
      className={cn("detail-identity-card h-full", className)}
    >
      <DetailFieldGrid>{children}</DetailFieldGrid>
    </DetailCard>
  )
}
