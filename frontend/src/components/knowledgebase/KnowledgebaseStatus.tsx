import { CheckCircle2, Cloud, Database } from "lucide-react"

import { TimeDisplay } from "@/components/ui/time-display"
import { databaseLogo } from "@/lib/database-logos"
import { shortCount } from "@/lib/detail-formatters"
import { knowledgebaseSourceDetails, type KnowledgebaseStatusPayload } from "@/lib/knowledgebase-status"
import { appPath } from "@/lib/runtime-paths"

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
    <div className="overflow-hidden rounded-md border border-border bg-card">
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
        <table className="w-full min-w-[42rem] border-collapse text-left type-table-cell">
          <thead className="bg-muted/80 type-table-header text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Source</th><th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Release</th><th className="px-3 py-2 text-right">Records</th>
              <th className="px-3 py-2 text-right">Collections</th>
              {!compact && <th className="px-3 py-2">Published</th>}
              <th className="px-3 py-2 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {releases.map((release) => {
              const details = knowledgebaseSourceDetails(release.source)
              const logo = databaseLogo(release.source)
              return (
                <tr key={release.source} className="border-t border-border/70 hover:bg-muted/35">
                  <td className="px-3 py-2"><div className="flex min-w-0 items-center gap-2">
                    {logo ? <img src={appPath(logo.src)} alt={logo.alt} className="h-5 w-14 object-contain" /> : <Database className="size-4 text-muted-foreground" />}
                    <span className="type-body-sm truncate text-foreground">{details.family}</span>
                  </div></td>
                  <td className="px-3 py-2 capitalize text-muted-foreground">{details.product}</td>
                  <td className="px-3 py-2 font-medium">{release.release}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{shortCount(release.records)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{release.collections?.length || 0}</td>
                  {!compact && <td className="px-3 py-2 text-muted-foreground">{release.published_at ? <TimeDisplay value={release.published_at} /> : "-"}</td>}
                  <td className="px-3 py-2 text-center">{release.status === "configured" ? <Cloud className="mx-auto size-4 text-info" aria-label="Configured remote service" /> : <CheckCircle2 className="mx-auto size-4 text-pass" aria-label="Installed" />}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
