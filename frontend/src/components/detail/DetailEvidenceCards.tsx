import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react"
import { type ReactNode, useState } from "react"
import { DetailCard } from "@/components/detail/FindingDetailLayout"
import { displayValue, isPresent } from "@/lib/detail-formatters"
import { cn } from "@/lib/utils"

export type DetailMetric = {
  label: string
  value: unknown
  href?: string
  monospace?: boolean
}

export type DetailColumn<T> = {
  key: string
  header: string
  render: (row: T, index: number) => ReactNode
  className?: string
}

function TableDisclosure({
  shown,
  total,
  initialRows,
  expanded,
  onToggle,
}: {
  shown: number
  total: number
  initialRows: number
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border/70 bg-muted/35 px-3 py-1.5">
      <span className="type-meta text-muted-foreground">
        Showing {shown} of {total}
      </span>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 type-label font-semibold text-primary interaction-transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        {expanded ? `Show first ${initialRows}` : `Show all ${total}`}
      </button>
    </div>
  )
}

export function DetailMetricTable({
  metrics,
  dense = false,
  initialRows,
}: {
  metrics: DetailMetric[]
  dense?: boolean
  initialRows?: number
}) {
  const [expanded, setExpanded] = useState(false)
  const visible = metrics.filter((metric) => isPresent(metric.value) || metric.href)
  if (visible.length === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>
  }

  const hasMoreRows = initialRows != null && initialRows > 0 && visible.length > initialRows
  const visibleMetrics = hasMoreRows && !expanded ? visible.slice(0, initialRows) : visible

  return (
    <div className="overflow-hidden rounded-lg border border-border/70">
      <table className="type-table-cell w-full border-collapse text-left">
        <tbody className="divide-y divide-border/60">
          {visibleMetrics.map((metric) => (
            <tr key={metric.label} className="bg-background/45 align-top">
              <th className={cn("w-36 px-3 font-medium uppercase tracking-wide text-muted-foreground", dense ? "py-0.5" : "py-1")}>
                {metric.label}
              </th>
              <td className={cn("px-3 font-semibold text-foreground", dense ? "py-0.5" : "py-1", metric.monospace && "")}>
                {metric.href ? (
                  <a
                    className="link-text inline-flex min-w-0 items-center gap-1"
                    href={metric.href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="truncate">{displayValue(metric.value, metric.href)}</span>
                    <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                  </a>
                ) : (
                  displayValue(metric.value)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {hasMoreRows ? (
        <TableDisclosure
          shown={visibleMetrics.length}
          total={visible.length}
          initialRows={initialRows}
          expanded={expanded}
          onToggle={() => setExpanded((current) => !current)}
        />
      ) : null}
    </div>
  )
}

export function DetailDataTable<T>({
  rows,
  columns,
  empty = "No data available.",
  initialRows,
}: {
  rows: T[]
  columns: DetailColumn<T>[]
  empty?: string
  initialRows?: number
}) {
  const [expanded, setExpanded] = useState(false)

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }

  const hasMoreRows = initialRows != null && initialRows > 0 && rows.length > initialRows
  const visibleRows = hasMoreRows && !expanded ? rows.slice(0, initialRows) : rows

  return (
    <div className="overflow-hidden rounded-lg border border-border/70">
      <div className="overflow-x-auto">
        <table className="type-table-cell w-full min-w-max border-separate border-spacing-0 text-left">
          <thead className="type-table-header bg-muted text-foreground dark:bg-muted/70">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={cn("border-b-2 border-border px-2.5 py-1", column.className)}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-background/55">
            {visibleRows.map((row, index) => (
              <tr key={index} className="align-top odd:bg-background/35 even:bg-card/50 hover:bg-muted/35">
                {columns.map((column) => (
                  <td key={column.key} className={cn("border-b border-border/55 px-2.5 py-1", column.className)}>
                    {column.render(row, index)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMoreRows ? (
        <TableDisclosure
          shown={visibleRows.length}
          total={rows.length}
          initialRows={initialRows}
          expanded={expanded}
          onToggle={() => setExpanded((current) => !current)}
        />
      ) : null}
    </div>
  )
}

export function EvidenceBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode
  tone?: "neutral" | "success" | "warning" | "danger" | "info"
}) {
  const toneClass = {
    neutral: "bg-muted text-muted-foreground",
    success: "bg-pass/12 text-pass",
    warning: "bg-warn/14 text-warn",
    danger: "bg-fail/12 text-fail",
    info: "bg-primary/10 text-primary",
  }[tone]

  return (
    <span className={cn("inline-flex max-w-full whitespace-normal break-words rounded-md px-2 py-0.5 type-meta font-semibold uppercase tracking-wide", toneClass)}>
      {children}
    </span>
  )
}

export function ExternalLinksCard({
  links,
  title = "External Evidence",
  children,
}: {
  links: DetailMetric[]
  title?: string
  children?: ReactNode
}) {
  const visible = links.filter((link) => link.href)
  if (!visible.length && !children) return null

  return (
    <DetailCard title={title} tone="info">
      <div className="space-y-3">
        {visible.length ? (
          <div>
            {children ? <h4 className="mb-1.5 type-label font-semibold uppercase text-muted-foreground">Resources</h4> : null}
            <div className="grid grid-cols-1 gap-2">
              {visible.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className="link-text flex min-w-0 items-center justify-between gap-2 rounded-lg border border-border bg-background/60 px-3 py-2 text-sm font-semibold transition-colors hover:bg-primary/10"
                >
                  <span className="min-w-0 break-words">{link.label}</span>
                  <ExternalLink className="h-4 w-4 shrink-0" />
                </a>
              ))}
            </div>
          </div>
        ) : null}
        {children}
      </div>
    </DetailCard>
  )
}
