import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"
import { useState } from "react"
import { shortCount } from "@/lib/detail-formatters"
import { donutMotion, donutTooltipLayer } from "@/components/plots/chart-options"
import type { CompositionItem } from "@/components/plots/chart-data"

export type KnowledgebaseSourceStatistics = {
  key: string
  name: string
  available: boolean
  total: number
  unit: string
  distribution: CompositionItem[]
  metrics: CompositionItem[]
}

const sourceChartColors = [
  "var(--color-tier3)",
  "var(--color-pass)",
  "var(--color-panel)",
  "var(--color-warning)",
  "var(--color-rna)",
  "var(--color-germline)",
]

function KnowledgebaseSourceDonut({ source }: { source: KnowledgebaseSourceStatistics }) {
  const [activeName, setActiveName] = useState<string | null>(null)
  const distribution = source.distribution.filter((row) => row.value > 0)
  const rows = distribution.length ? distribution : source.metrics.filter((row) => row.value > 0)
  const isFeatureCoverage = !distribution.length
  if (!rows.length) {
    return <div className="flex h-40 items-center justify-center type-body-sm text-muted-foreground">{shortCount(source.total)} {source.unit}</div>
  }
  return (
    <div className="grid min-w-0 items-center gap-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
      <div className="relative h-44 w-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            {isFeatureCoverage ? rows.slice(0, 3).map((metric, ringIndex) => (
              <Pie
                key={metric.name}
                data={[metric, { name: `Without ${metric.name}`, value: Math.max(0, source.total - metric.value) }]}
                dataKey="value"
                nameKey="name"
                innerRadius={30 + ringIndex * 17}
                outerRadius={42 + ringIndex * 17}
                paddingAngle={2}
                cornerRadius={3}
                stroke="none"
                {...donutMotion}
              >
                {[metric.name, `Without ${metric.name}`].map((name, index) => (
                  <Cell
                    key={name}
                    fill={index ? "var(--color-unknown)" : sourceChartColors[ringIndex % sourceChartColors.length]}
                    onMouseEnter={() => setActiveName(name)}
                    onMouseLeave={() => setActiveName(null)}
                    style={{ opacity: activeName && activeName !== name ? 0.35 : 1, transition: "opacity 180ms ease" }}
                  />
                ))}
              </Pie>
            )) : (
              <Pie data={rows} dataKey="value" nameKey="name" innerRadius={48} outerRadius={76} paddingAngle={3} cornerRadius={4} stroke="none" {...donutMotion}>
                {rows.map((row, index) => (
                  <Cell
                    key={row.name}
                    fill={sourceChartColors[index % sourceChartColors.length]}
                    onMouseEnter={() => setActiveName(row.name)}
                    onMouseLeave={() => setActiveName(null)}
                    style={{
                      cursor: "pointer",
                      opacity: activeName && activeName !== row.name ? 0.35 : 1,
                      filter: activeName === row.name ? "drop-shadow(0 2px 4px color-mix(in srgb, var(--foreground) 28%, transparent))" : "none",
                      transition: "opacity 180ms ease, filter 180ms ease",
                    }}
                  />
                ))}
              </Pie>
            )}
            <Tooltip formatter={(value, name) => [`${shortCount(value)} genes`, String(name)]} wrapperStyle={donutTooltipLayer} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <strong className="text-lg font-semibold tabular-nums">{shortCount(source.total)}</strong>
          <span className="type-label uppercase text-muted-foreground">{source.unit}</span>
        </div>
      </div>
      <div className="min-w-0 space-y-2">
        {rows.map((row, index) => (
          <div key={row.name} className="flex min-w-0 items-center gap-2 type-meta">
            <i className="size-2.5 shrink-0 rounded-sm" style={{ backgroundColor: sourceChartColors[index % sourceChartColors.length] }} />
            <span className="min-w-0 flex-1 truncate" title={row.name}>{row.name}</span>
            <strong className="tabular-nums">{shortCount(row.value)}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

export function KnowledgebaseStatisticsCharts({ sources }: { sources: KnowledgebaseSourceStatistics[] }) {
  const available = sources.filter((source) => source.available)
  if (!available.length) return <p className="type-body-sm text-muted-foreground">No aggregate source statistics are available.</p>
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {available.map((source) => (
        <section key={source.key} className="dashboard-subcard min-w-0 overflow-hidden">
          <header className="border-b border-border bg-muted/70 px-3 py-2">
            <h3 className="type-card-title text-foreground">{source.name}</h3>
          </header>
          <div className="p-3"><KnowledgebaseSourceDonut source={source} /></div>
        </section>
      ))}
    </div>
  )
}
