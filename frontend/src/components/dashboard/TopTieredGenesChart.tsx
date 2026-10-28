import { Link } from "react-router-dom"
import { TableBadge } from "@/components/ui/table-badge"
import { nomenclatureLabel } from "@/lib/application-constants"
import { shortCount } from "@/lib/detail-formatters"

type TieredGeneDatum = {
  gene: string
  total: number
  tier1?: number
  tier2?: number
  tier3?: number
  tier4?: number
  nomenclatures?: string[]
}

const tierColors = [
  "var(--color-tier1)",
  "var(--color-tier2)",
  "var(--color-tier3)",
  "var(--color-tier4)",
]

export function TopTieredGenesChart({ data }: { data: TieredGeneDatum[] }) {
  const maximum = Math.max(...data.map((row) => Number(row.total || 0)), 1)

  return (
    <div className="space-y-2" role="list" aria-label="Top tiered genes ranked by unique classified findings">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-2">
        <p className="type-meta text-muted-foreground">Bar length represents each gene's total relative to the leading gene.</p>
        <div className="flex flex-wrap items-center gap-3 type-meta text-muted-foreground" aria-label="Tier legend">
          {tierColors.map((color, index) => (
            <span key={color} className="inline-flex items-center gap-1">
              <i className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
              Tier {index + 1}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-x-5 gap-y-2.5 xl:grid-cols-2">
        {data.map((row, index) => {
          const tiers = [
            Number(row.tier1 || 0),
            Number(row.tier2 || 0),
            Number(row.tier3 || 0),
            Number(row.tier4 || 0),
          ]
          const total = Math.max(Number(row.total || 0), tiers.reduce((sum, count) => sum + count, 0))
          const width = `${Math.max(4, (total / maximum) * 100)}%`
          const tierSummary = tiers
            .map((count, tierIndex) => count > 0 ? `Tier ${tierIndex + 1}: ${count}` : null)
            .filter(Boolean)
            .join(", ")

          return (
            <article
              key={row.gene}
              role="listitem"
              aria-label={`${index + 1}. ${row.gene}, ${total} unique findings. ${tierSummary}`}
              className="dashboard-subcard grid min-w-0 grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1.5 p-2.5"
            >
              <span className="row-span-2 flex h-7 w-7 items-center justify-center rounded-full bg-muted type-label text-muted-foreground">
                {index + 1}
              </span>
              <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                <Link
                  to={`/variants/gene-cohort?gene=${encodeURIComponent(row.gene)}`}
                  className="truncate text-sm font-semibold text-link hover:underline"
                >
                  {row.gene}
                </Link>
                {(row.nomenclatures || []).filter(Boolean).sort().map((value) => (
                  <TableBadge key={value} className="border-border bg-muted/60 text-foreground shadow-none">
                    {nomenclatureLabel(value)}
                  </TableBadge>
                ))}
              </div>
              <strong className="row-span-2 self-center text-base font-semibold tabular-nums text-foreground" title={`${total} unique classified findings`}>
                {shortCount(total)}
              </strong>
              <div className="min-w-0">
                <div className="progress-pipe h-3 w-full overflow-hidden rounded-full" title={tierSummary}>
                  <div className="flex h-full overflow-hidden rounded-full" style={{ width }}>
                    {tiers.map((count, tierIndex) => count > 0 && (
                      <span
                        key={tierIndex}
                        className="progress-pipe-segment h-full min-w-px"
                        style={{
                          backgroundColor: tierColors[tierIndex],
                          width: `${(count / Math.max(total, 1)) * 100}%`,
                        }}
                        title={`Tier ${tierIndex + 1}: ${count}`}
                      />
                    ))}
                  </div>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 type-meta text-muted-foreground">
                  {tiers.map((count, tierIndex) => count > 0 && (
                    <span key={tierIndex}>T{tierIndex + 1} <strong className="font-semibold text-foreground">{count}</strong></span>
                  ))}
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
