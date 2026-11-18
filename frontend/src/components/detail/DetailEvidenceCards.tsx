// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Table, TableBody, TableRow, TableHead, TableCell, TableHeader } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { icon } from "@/lib/assets"
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
      <Button variant="ghost" size="sm"
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        {expanded ? <icon.chevronUp className="size-3.5" /> : <icon.chevronDown className="size-3.5" />}
        {expanded ? `Show first ${initialRows}` : `Show all ${total}`}
      </Button>
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
    <div className="table-frame">
      <Table density={dense ? "compact" : "standard"}>
        <TableBody>
          {visibleMetrics.map((metric) => (
            <TableRow key={metric.label} className="align-top">
              <TableHead scope="row" className="w-36 font-medium uppercase tracking-wide text-muted-foreground">
                {metric.label}
              </TableHead>
              <TableCell className={cn("font-semibold text-foreground", metric.monospace && "font-mono")}>
                {metric.href ? (
                  <a
                    className="link-text inline-flex min-w-0 items-center gap-1"
                    href={metric.href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="truncate">{displayValue(metric.value, metric.href)}</span>
                    <icon.externalLink className="h-3.5 w-3.5 shrink-0" />
                  </a>
                ) : (
                  displayValue(metric.value)
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
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
  tableLayout = "auto",
}: {
  rows: T[]
  columns: DetailColumn<T>[]
  empty?: string
  initialRows?: number
  tableLayout?: "auto" | "fixed"
}) {
  const [expanded, setExpanded] = useState(false)

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }

  const hasMoreRows = initialRows != null && initialRows > 0 && rows.length > initialRows
  const visibleRows = hasMoreRows && !expanded ? rows.slice(0, initialRows) : rows

  return (
    <div className="table-frame">
      <div className="overflow-x-auto">
        <Table className={cn(tableLayout === "fixed" ? "table-fixed" : "min-w-max")}>
          <TableHeader className="text-foreground">
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column.key} className={cn(column.className)}>
                  {column.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleRows.map((row, index) => (
              <TableRow key={index} className="align-top">
                {columns.map((column) => (
                  <TableCell key={column.key} className={cn(column.className)}>
                    {column.render(row, index)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
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
  return (
    <Badge variant={tone} className="min-w-0 whitespace-normal uppercase tracking-wide [overflow-wrap:anywhere]">
      {children}
    </Badge>
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
                  <icon.externalLink className="h-4 w-4 shrink-0" />
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
