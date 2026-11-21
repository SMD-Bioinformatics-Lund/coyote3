// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { DataTable } from "@/components/data-table/DataTable"
import type { CoverageIntervalPayload } from "@/lib/generated"
import { shortCount } from "@/lib/detail-formatters"
import type { ColumnDef } from "@tanstack/react-table"
import { coord } from "./coverage-presentation"

export function IntervalCoverageView({ intervals, cutoff, sampleId }: {
  intervals: CoverageIntervalPayload[]
  cutoff: number
  sampleId: string
}) {
  const lowCount = intervals.filter(row => row.avg_cov !== null && row.avg_cov < cutoff).length
  const unknownCount = intervals.filter(row => row.avg_cov === null).length
  const columns: ColumnDef<CoverageIntervalPayload>[] = [
    { id: "region", header: "Chromosomal region", accessorFn: coord },
    { id: "size", header: "Size (bp)", accessorFn: row => row.end - row.start + 1 },
    {
      id: "avg_cov", header: "Average depth (×)",
      accessorFn: row => row.avg_cov ?? undefined,
      sortUndefined: "last",
      cell: ({ row }) => {
        const value = row.original.avg_cov
        return <span className={value === null ? "text-muted-foreground" : value < cutoff ? "font-semibold text-fail" : "text-pass"}>
          {value === null ? "—" : value.toFixed(1)}
        </span>
      },
    },
    { accessorKey: "amplicon", header: "Amplicon", cell: ({ row }) => row.original.amplicon ?? "—" },
  ]
  return <SurfacePanel title="Legacy interval coverage" description="Coverage intervals retained from the original analysis.">
    <div className="grid gap-2 sm:grid-cols-3">
      <MetricCard title="Stored intervals" value={shortCount(intervals.length)} />
      <MetricCard title={`Below ${cutoff}×`} value={shortCount(lowCount)} />
      <MetricCard title="Unknown depth" value={shortCount(unknownCount)} />
    </div>
    <DataTable columns={columns} data={intervals} filename={`coverage_${sampleId}.csv`}
      emptyMessage="No legacy coverage intervals are stored for this sample." />
  </SurfacePanel>
}
