// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
import { icon } from "@/lib/assets"
import { TimeDisplay } from "@/components/ui/time-display"
import { DatabaseBrand } from "@/components/knowledgebase/DatabaseBrand"
import { shortCount } from "@/lib/detail-formatters"
import { knowledgebaseSourceDetails, type KnowledgebaseStatusPayload } from "@/lib/knowledgebase-status"

export type { KnowledgebaseStatusPayload } from "@/lib/knowledgebase-status"

export function KnowledgebaseStatus({
  payload,
  compact = false,
}: {
  payload?: KnowledgebaseStatusPayload
  compact?: boolean
}) {
  const releases = payload?.releases || []
  const totalRecords = payload?.summary?.total_records
    ?? releases.reduce((total, release) => total + Number(release.records || 0), 0)

  if (!releases.length) {
    return (
      <div className="bg-card px-4 py-5 text-center type-body-sm text-muted-foreground">
        No installed knowledgebase releases are recorded.
      </div>
    )
  }

  return (
    <div className="paper-surface overflow-hidden rounded-md">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-border bg-success/5 px-3 py-2">
        <div className="flex items-baseline gap-1.5">
          <span className="type-card-title text-primary">
            {shortCount(payload?.summary?.available_products ?? releases.length)}
          </span>
          <span className="type-meta text-muted-foreground">available products</span>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="type-card-title text-foreground">{shortCount(totalRecords)}</span>
          <span className="type-meta text-muted-foreground">indexed records</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <Table className="min-w-[42rem]">
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead><TableHead>Product</TableHead>
              <TableHead>Release</TableHead><TableHead className="text-right">Records</TableHead>
              <TableHead className="text-right">Collections</TableHead>
              {!compact && <TableHead>Published</TableHead>}
              <TableHead className="text-center">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {releases.map((release) => {
              const details = knowledgebaseSourceDetails(release.source)
              return (
                <TableRow key={release.source}>
                  <TableCell><DatabaseBrand source={release.source} label={details.family}
                    className="type-body-sm text-foreground" logoClassName="h-5 w-14" /></TableCell>
                  <TableCell className="capitalize text-muted-foreground">{details.product}</TableCell>
                  <TableCell className="font-medium">{release.release}</TableCell>
                  <TableCell className="text-right tabular-nums">{shortCount(release.records)}</TableCell>
                  <TableCell className="text-right tabular-nums">{release.collections?.length || 0}</TableCell>
                  {!compact && <TableCell className="text-muted-foreground">{release.published_at ? <TimeDisplay value={release.published_at} /> : "-"}</TableCell>}
                  <TableCell className="text-center">{release.status === "configured" ? <icon.cloud className="mx-auto size-4 text-info" aria-label="Configured remote service" /> : <icon.checkCircle2 className="mx-auto size-4 text-pass" aria-label="Installed" />}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
