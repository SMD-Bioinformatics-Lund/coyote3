import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export function AnalysisTableCard({
  header,
  filterPanel,
  children,
  className,
}: {
  header?: ReactNode
  filterPanel?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn("glass-card flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden p-3", className)}
      data-testid="analysis-table-card"
    >
      {header ? (
        <div className="mb-2 flex min-h-9 shrink-0 items-center justify-between gap-3 border-b border-border px-1 pb-2">
          {header}
        </div>
      ) : null}
      {filterPanel ? <div className="mb-3 shrink-0">{filterPanel}</div> : null}
      {children}
    </div>
  )
}
