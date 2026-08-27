import { type ReactNode } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, Fingerprint } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageFrame } from "@/components/layout/PageFrame"
import { ExpandableText } from "@/components/detail/ExpandableText"
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
  return <PageFrame className="flex-1">{children}</PageFrame>
}

export function DetailHero({
  backTo,
  eyebrow,
  title,
  chips,
  actions,
  statLabel,
  statValue,
  density = "default",
}: {
  backTo: string
  eyebrow?: ReactNode
  title: ReactNode
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
        <Link
          to={backTo}
          className="
            inline-flex h-8 w-8 shrink-0 self-start items-center justify-center
            rounded-full
            border border-border
            bg-card
            text-muted-foreground
            interaction-transition
            hover:bg-surface-hover
            hover:text-foreground
          "
          aria-label="Back to samples"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>

        <div className="min-w-0 flex-1">
          {eyebrow && (
            <p className="type-page-eyebrow lowercase mb-1 text-muted-foreground">
              {eyebrow}
            </p>
          )}
          <h1 className="type-page-title min-w-0">
            <span className="brand-gradient-text">{title}</span>
          </h1>
          {chips && <div className="detail-hero-callers mt-2 flex flex-wrap items-center gap-2">{chips}</div>}
        </div>

        {(actions || statValue) && (
          <div className="flex shrink-0 flex-col items-start gap-3 md:ml-auto md:self-start md:items-end">
            {statValue && (
              <div className="flex flex-col items-start md:items-end">
                {statLabel && (
                  <span className="type-label mb-1 text-muted-foreground">
                    {statLabel}
                  </span>
                )}

                <span className="detail-stat-positive">
                  {statValue}
                </span>
              </div>
            )}

            {actions && (
              <div className="flex flex-wrap items-center justify-start gap-2 md:justify-end">
                {actions}
              </div>
            )}
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

export function FindingDetailHero({
  backTo,
  genes,
  identity,
  sampleHref,
  sampleName,
  callers,
  actions,
  statLabel,
  statValue,
}: {
  backTo: string
  genes: string[]
  identity: string
  sampleHref: string
  sampleName: ReactNode
  callers?: ReactNode
  actions?: ReactNode
  statLabel?: ReactNode
  statValue?: ReactNode
}) {
  const visibleGenes = genes.map((gene) => String(gene || "").trim()).filter(Boolean)

  return (
    <div className="detail-hero">
      <div className="detail-hero-row relative z-10 flex min-h-32 flex-col gap-3 md:flex-row md:items-stretch">
        <Link
          to={backTo}
          className="inline-flex h-8 w-8 shrink-0 self-start items-center justify-center rounded-full border border-border bg-card text-muted-foreground interaction-transition hover:bg-surface-hover hover:text-foreground"
          aria-label="Back to findings"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>

        <div className="min-w-0 flex-1">
          <div className="type-card-title mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
            {(visibleGenes.length ? visibleGenes : ["Intergenic finding"]).map((gene, index) => (
              visibleGenes.length ? (
                <span key={`${gene}-${index}`} className="inline-flex items-center gap-2">
                  {index > 0 && <span className="text-muted-foreground">/</span>}
                  <Link
                    to={`/public/gene/${encodeURIComponent(gene)}/info`}
                    className="brand-gradient-text interaction-transition hover:opacity-80 focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {gene}
                  </Link>
                </span>
              ) : <span key={gene} className="text-muted-foreground">{gene}</span>
            ))}
          </div>
          <h1 className="type-page-title min-w-0 text-foreground">
            <ExpandableText text={identity || "Unknown finding"} maxLength={56} className="inline-flex max-w-full" />
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Link to={sampleHref} className="detail-hero-sample-chip">
              Sample {sampleName}
            </Link>
          </div>
        </div>

        {(actions || statValue || callers) && (
          <div className="flex shrink-0 flex-col items-start gap-2.5 md:ml-auto md:min-w-52 md:items-end md:pl-4 md:pr-2 lg:pr-3">
            {statValue && (
              <div className="flex flex-col items-start md:items-end">
                {statLabel && <span className="type-label mb-1 text-muted-foreground">{statLabel}</span>}
                <span className="detail-stat-positive">{statValue}</span>
              </div>
            )}
            {callers}
            {actions && <div className="mt-auto flex flex-wrap items-center justify-start gap-2 pt-1 md:justify-end">{actions}</div>}
          </div>
        )}
      </div>
    </div>
  )
}

export function FindingCallerMeta({ children }: { children: ReactNode }) {
  return (
    <div className="detail-hero-caller-meta flex flex-wrap items-center gap-1.5 md:justify-end">
      <span className="type-meta font-medium uppercase tracking-wide text-muted-foreground">Called by</span>
      {children}
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
