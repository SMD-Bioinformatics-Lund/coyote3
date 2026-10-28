import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"
import { useState } from "react"
import { shortCount } from "@/lib/detail-formatters"
import { donutMotion, donutTooltipLayer } from "@/components/plots/chart-options"
import type { CompositionItem } from "@/components/plots/chart-data"

export type CancerGeneCensusSummary = {
  available: boolean
  total_genes: number
  tiers: CompositionItem[]
  origins: CompositionItem[]
  roles: CompositionItem[]
  mutation_types: CompositionItem[]
  molecular_genetics: CompositionItem[]
  hallmarks: CompositionItem[]
  hallmark_records: number
}

const censusTierColors = [
  "var(--color-tier1)",
  "var(--color-tier2)",
  "var(--color-tier3)",
  "var(--color-tierother)",
]
const censusOriginColors = [
  "var(--color-somatic)",
  "var(--color-germline)",
  "var(--color-panel)",
  "var(--color-unknown)",
]
const censusRoleColors = [
  "var(--color-tier3)",
  "var(--color-tier4)",
  "var(--color-rna)",
  "var(--color-panel)",
  "var(--color-tier2)",
  "var(--color-dna)",
  "var(--color-tierother)",
  "var(--color-unknown)",
]

function censusTierColor(row: CompositionItem, index: number) {
  const tier = Number(row.name.match(/\d+/)?.[0])
  return tier >= 1 && tier <= 4
    ? `var(--color-tier${tier})`
    : censusTierColors[index % censusTierColors.length]
}

function censusOriginColor(row: CompositionItem, index: number) {
  const colors: Record<string, string> = {
    "Somatic only": "var(--color-somatic)",
    "Germline only": "var(--color-germline)",
    "Somatic and germline": "var(--color-panel)",
    "Not specified": "var(--color-unknown)",
  }
  return colors[row.name] || censusOriginColors[index % censusOriginColors.length]
}

function censusRoleColor(_row: CompositionItem, index: number) {
  return censusRoleColors[index % censusRoleColors.length]
}

function CensusLegend({
  title,
  rows,
  colorFor,
}: {
  title: string
  rows: CompositionItem[]
  colorFor: (row: CompositionItem, index: number) => string
}) {
  return (
    <section className="min-w-0">
      <h3 className="type-label mb-1.5 text-muted-foreground">{title}</h3>
      <ul className="space-y-1">
        {rows.map((row, index) => (
          <li key={row.name} className="flex min-w-0 items-center gap-1.5 type-meta">
            <i
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: colorFor(row, index) }}
            />
            <span className="min-w-0 flex-1 truncate text-muted-foreground" title={row.name}>
              {row.name}
            </span>
            <strong className="shrink-0 font-semibold tabular-nums text-foreground">
              {shortCount(row.value)}
            </strong>
          </li>
        ))}
      </ul>
    </section>
  )
}

function CensusRankedTerms({ title, rows }: { title: string; rows: CompositionItem[] }) {
  if (!rows.length) return null
  const maximum = Math.max(...rows.map((row) => row.value), 1)
  return (
    <section className="dashboard-subcard min-w-0 p-3">
      <h3 className="type-label mb-2 text-muted-foreground">{title}</h3>
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.name} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 type-meta">
            <span className="truncate text-foreground" title={row.name}>{row.name}</span>
            <strong className="font-semibold tabular-nums text-foreground">{shortCount(row.value)}</strong>
            <div className="progress-pipe col-span-2 h-2 overflow-hidden rounded-full">
              <div
                className="progress-pipe-fill h-full rounded-full bg-panel"
                style={{ width: `${Math.max(3, (row.value / maximum) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function CancerGeneCensusChart({ data }: { data: CancerGeneCensusSummary }) {
  const [activeSegment, setActiveSegment] = useState<string | null>(null)
  const cellStyle = (key: string) => ({
    cursor: "pointer",
    opacity: activeSegment && activeSegment !== key ? 0.38 : 1,
    filter: activeSegment === key ? "drop-shadow(0 2px 4px color-mix(in srgb, var(--foreground) 28%, transparent))" : "none",
    transition: "opacity 180ms ease, filter 180ms ease",
  })
  const accessibleSummary = [
    ...data.tiers.map((row) => `${row.name}: ${row.value}`),
    ...data.origins.map((row) => `${row.name}: ${row.value}`),
    ...data.roles.map((row) => `${row.name}: ${row.value}`),
  ].join("; ")
  const hallmarkTitle = data.hallmark_records
    ? `Hallmarks - ${shortCount(data.hallmark_records)} ${data.hallmark_records === 1 ? "record" : "records"}`
    : "Hallmarks"

  return (
    <div className="min-w-0 space-y-3">
      <div className="dashboard-subcard grid min-w-0 items-center gap-4 p-4 lg:grid-cols-[minmax(26rem,1fr)_18rem]">
        <div
          className="relative h-[26rem] w-full max-w-[42rem] min-w-0 justify-self-center"
          role="img"
          aria-label={`Cancer Gene Census summary for ${data.total_genes} genes. ${accessibleSummary}`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <Pie
                data={data.roles}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                startAngle={90}
                endAngle={-270}
                innerRadius="73%"
                outerRadius="91%"
                paddingAngle={2}
                cornerRadius={3}
                stroke="none"
                {...donutMotion}
              >
                {data.roles.map((row, index) => (
                  <Cell key={row.name} fill={censusRoleColor(row, index)} style={cellStyle(`role:${row.name}`)} onMouseEnter={() => setActiveSegment(`role:${row.name}`)} onMouseLeave={() => setActiveSegment(null)} />
                ))}
              </Pie>
              <Pie
                data={data.origins}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                startAngle={90}
                endAngle={-270}
                innerRadius="52%"
                outerRadius="68%"
                paddingAngle={2}
                cornerRadius={3}
                stroke="none"
                {...donutMotion}
              >
                {data.origins.map((row, index) => (
                  <Cell key={row.name} fill={censusOriginColor(row, index)} style={cellStyle(`origin:${row.name}`)} onMouseEnter={() => setActiveSegment(`origin:${row.name}`)} onMouseLeave={() => setActiveSegment(null)} />
                ))}
              </Pie>
              <Pie
                data={data.tiers}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                startAngle={90}
                endAngle={-270}
                innerRadius="31%"
                outerRadius="47%"
                paddingAngle={2}
                cornerRadius={3}
                stroke="none"
                {...donutMotion}
              >
                {data.tiers.map((row, index) => (
                  <Cell key={row.name} fill={censusTierColor(row, index)} style={cellStyle(`tier:${row.name}`)} onMouseEnter={() => setActiveSegment(`tier:${row.name}`)} onMouseLeave={() => setActiveSegment(null)} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name) => [`${shortCount(value)} genes`, String(name)]}
                contentStyle={{ borderRadius: "8px", border: "1px solid var(--border)", fontSize: 11 }}
                wrapperStyle={donutTooltipLayer}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <strong className="text-xl font-semibold tabular-nums text-foreground">{shortCount(data.total_genes)}</strong>
            <span className="type-label uppercase text-muted-foreground">genes</span>
          </div>
        </div>
        <div className="grid content-center gap-3 self-center lg:justify-self-end">
          <CensusLegend title="Inner ring - CGC tier" rows={data.tiers} colorFor={censusTierColor} />
          <CensusLegend title="Middle ring - origin scope" rows={data.origins} colorFor={censusOriginColor} />
          <CensusLegend title="Outer ring - role in cancer" rows={data.roles} colorFor={censusRoleColor} />
        </div>
      </div>

      <div className="grid min-w-0 items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
        <CensusRankedTerms title="Mutation types" rows={data.mutation_types} />
        <CensusRankedTerms title="Molecular genetics" rows={data.molecular_genetics} />
        <CensusRankedTerms title={hallmarkTitle} rows={data.hallmarks} />
      </div>
    </div>
  )
}
