import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, ScatterChart, Scatter } from "recharts"
import { Link } from "react-router-dom"
import { useState } from "react"
import { ChartPanel } from "@/components/plots/ChartPanel"
import { TableBadge } from "@/components/ui/table-badge"
import { nomenclatureLabel } from "@/lib/application-constants"
import { shortCount } from "@/lib/detail-formatters"

type ChartProps = {
  colors: string[]
}

type CompositionItem = {
  name: string
  value: number
}

type CompositionGroup = {
  name: string
  rows: CompositionItem[]
}

type PipelineDatum = {
  name?: string | null
  version?: string | null
  count?: number | null
  analysed?: number | null
}

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

export type KnowledgebaseSourceStatistics = {
  key: string
  name: string
  available: boolean
  total: number
  unit: string
  distribution: CompositionItem[]
  metrics: CompositionItem[]
}

const donutMotion = {
  isAnimationActive: true,
  animationBegin: 0,
  animationDuration: 700,
  animationEasing: "ease-out" as const,
}

const donutTooltipLayer = {
  zIndex: 40,
}

function CompositionDonut({ group, colors, colorOffset }: { group: CompositionGroup; colors: string[]; colorOffset: number }) {
  const rows = group.rows.filter((row) => row.value > 0)
  const total = rows.reduce((sum, row) => sum + row.value, 0)

  return (
    <figure className="min-w-0 border-b border-border/60 pb-3 last:border-b-0 md:border-b-0 md:border-r md:pr-3 md:last:border-r-0">
      <figcaption className="type-label mb-1.5 text-muted-foreground">{group.name}</figcaption>
      {rows.length ? (
        <div className="grid min-w-0 grid-cols-[8rem_minmax(0,1fr)] items-center gap-3">
          <div className="relative h-32 w-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={rows}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  startAngle={90}
                  endAngle={-270}
                  innerRadius={36}
                  outerRadius={58}
                  paddingAngle={4}
                  cornerRadius={3}
                  stroke="none"
                  {...donutMotion}
                >
                  {rows.map((row, index) => (
                    <Cell key={row.name} fill={colors[(colorOffset + index) % colors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [shortCount(value), String(name)]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid var(--border)", fontSize: 11 }}
                  wrapperStyle={donutTooltipLayer}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <strong className="text-sm font-semibold text-foreground">{shortCount(total)}</strong>
              <span className="type-label uppercase text-muted-foreground">samples</span>
            </div>
          </div>
          <ul className="min-w-0 space-y-1.5">
            {rows.map((row, index) => (
              <li key={row.name} className="flex min-w-0 items-center gap-1.5 type-meta">
                <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: colors[(colorOffset + index) % colors.length] }} />
                <span className="min-w-0 flex-1 truncate capitalize text-muted-foreground">{row.name || "unknown"}</span>
                <strong className="shrink-0 font-semibold text-foreground">{shortCount(row.value)}</strong>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="flex h-32 items-center justify-center text-xs text-muted-foreground">No data</div>
      )}
    </figure>
  )
}

export function SampleCompositionCharts({
  groups,
  pipelines,
  colors,
}: ChartProps & {
  groups: CompositionGroup[]
  pipelines: PipelineDatum[]
}) {
  const pipelineRows = pipelines
    .map((pipeline) => {
      const total = Math.max(0, Number(pipeline.count || 0))
      const analysed = Math.min(total, Math.max(0, Number(pipeline.analysed || 0)))
      const version = String(pipeline.version || "").trim()
      return {
        label: `${String(pipeline.name || "Unknown pipeline")}${version ? ` ${version}` : " (unversioned)"}`,
        Analysed: analysed,
        "Awaiting review": Math.max(0, total - analysed),
        Total: total,
      }
    })
    .sort((left, right) => right.Total - left.Total)

  const visiblePipelines = pipelineRows.slice(0, 8)
  if (pipelineRows.length > 8) {
    visiblePipelines.push(pipelineRows.slice(8).reduce((other, row) => ({
      label: `${pipelineRows.length - 8} other versions`,
      Analysed: other.Analysed + row.Analysed,
      "Awaiting review": other["Awaiting review"] + row["Awaiting review"],
      Total: other.Total + row.Total,
    }), { label: "", Analysed: 0, "Awaiting review": 0, Total: 0 }))
  }

  const pipelineSummary = visiblePipelines
    .map((pipeline) => `${pipeline.label}: ${pipeline.Analysed} analysed, ${pipeline["Awaiting review"]} awaiting review`)
    .join("; ")

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
        {groups.map((group, index) => (
          <CompositionDonut key={group.name} group={group} colors={colors} colorOffset={index * 2} />
        ))}
      </div>

      <div className="border-t border-border/70 pt-3">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="type-label text-foreground">Pipeline throughput</h3>
            <p className="type-meta mt-0.5 text-muted-foreground">Analysis completion by pipeline and version.</p>
          </div>
          <div className="flex items-center gap-3 type-label text-muted-foreground">
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-pass" />Analysed</span>
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-warning" />Awaiting review</span>
          </div>
        </div>
        {visiblePipelines.length ? (
          <div
            role="img"
            aria-label={`Pipeline throughput. ${pipelineSummary}`}
            style={{ height: Math.max(190, visiblePipelines.length * 34 + 42) }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={visiblePipelines} layout="vertical" margin={{ top: 4, right: 30, bottom: 4, left: 12 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.18} horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="label" width={148} tick={{ fontSize: 10 }} tickLine={false} />
                <Tooltip
                  formatter={(value, name) => [shortCount(value), String(name)]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid var(--border)", fontSize: 11 }}
                  cursor={{ fill: "var(--chart-tooltip-cursor)" }}
                />
                <Bar dataKey="Analysed" stackId="pipeline" fill="var(--color-pass)" radius={[4, 0, 0, 4]} isAnimationActive={false} />
                <Bar dataKey="Awaiting review" stackId="pipeline" fill="var(--color-warning)" radius={[0, 4, 4, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex h-36 items-center justify-center text-xs text-muted-foreground">No pipeline data available.</div>
        )}
      </div>
    </div>
  )
}

export function TierDistributionChart({
  data,
  colors,
}: ChartProps & {
  data: Array<{ name: string; value: number }>
}) {
  return (
    <ChartPanel
      title="Tier distribution"
      description="Current classification distribution."
      filename="tier_distribution"
      data={data}
    >
      <div className="h-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 4, right: 8, bottom: 8, left: 8 }}>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="45%"
              startAngle={90}
              endAngle={-270}
              innerRadius="42%"
              outerRadius="70%"
              paddingAngle={4}
              cornerRadius={3}
              stroke="none"
              {...donutMotion}
            >
              {data.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ borderRadius: "10px", border: "1px solid var(--color-border)" }}
              wrapperStyle={donutTooltipLayer}
            />
            <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 11, lineHeight: "18px" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  )
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
            <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-panel"
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

export function GeneCoverageChart({
  data,
}: {
  data: Array<{ name: string; Covered: number; Germline: number }>
}) {
  const covered = data.map((row) => ({ name: row.name, genes: row.Covered }))
  const germline = data.map((row) => ({ name: row.name, genes: row.Germline }))

  return (
    <ChartPanel
      title="Gene coverage per assay"
      description="Covered and germline gene scope from active ASP definitions."
      filename="gene_coverage_per_assay"
      data={data}
    >
      <div className="h-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart layout="vertical" margin={{ top: 12, right: 34, left: 16, bottom: 28 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.18} horizontal={false} />
            <XAxis
              type="number"
              dataKey="genes"
              name="Genes"
              allowDecimals={false}
              tick={{ fontSize: 10 }}
              label={{ value: "Gene assignments", position: "insideBottom", offset: -16, fontSize: 10 }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={148}
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              formatter={(value, name) => [shortCount(value), String(name)]}
              contentStyle={{ borderRadius: "10px", border: "1px solid var(--border)", fontSize: 11 }}
              cursor={{ stroke: "var(--border)", strokeDasharray: "3 3" }}
            />
            <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11 }} />
            <Scatter name="Covered genes" data={covered} fill="var(--color-panel)" isAnimationActive={false} />
            <Scatter name="Germline genes" data={germline} fill="var(--color-germline)" isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  )
}

export function PanelAnalysisCapabilityChart({
  data,
}: {
  data: Array<{ name: string; Enabled: number; Reportable: number }>
}) {
  const rows = data.map((row) => {
    const enabled = Math.max(0, row.Enabled)
    const reportable = Math.min(enabled, Math.max(0, row.Reportable))
    const percentage = enabled ? Math.round((reportable / enabled) * 100) : 0

    return {
      ...row,
      Enabled: enabled,
      Reportable: reportable,
      "Enabled only": enabled - reportable,
      percentage,
    }
  })
  const accessibleSummary = rows
    .map((row) => `${row.name}: ${row.Reportable} of ${row.Enabled} reportable, ${row.Enabled ? Math.round((row.Reportable / row.Enabled) * 100) : 0} percent`)
    .join("; ")

  return (
    <ChartPanel
      title="Panel analysis capability"
      description="Enabled and reportable analysis sections across active targeted-panel configurations."
      filename="panel_analysis_capability"
      data={data}
    >
      <div
        className="h-full min-h-0 overflow-x-auto"
        role="img"
        aria-label={`Panel analysis capability. ${accessibleSummary}`}
      >
        <svg
          viewBox="0 0 1120 260"
          className="h-full min-h-[230px] w-full min-w-[840px]"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          {rows.map((row, index) => {
            const cellWidth = 1120 / Math.max(rows.length, 1)
            const centerX = cellWidth * index + cellWidth / 2
            const centerY = 112
            const radius = 58
            const circumference = 2 * Math.PI * radius
            const progress = circumference * (row.percentage / 100)
            const enabledOnly = row["Enabled only"]

            return (
              <g key={row.name}>
                <title>{`${row.name}: ${row.Reportable} reportable of ${row.Enabled} enabled (${row.percentage}%). ${enabledOnly} enabled but not reportable.`}</title>
                <text
                  x={centerX}
                  y="20"
                  textAnchor="middle"
                  fill="var(--foreground)"
                  fontSize="11"
                  fontWeight="600"
                >
                  {row.name.replaceAll("_", " ")}
                </text>
                <circle
                  cx={centerX}
                  cy={centerY}
                  r={radius}
                  fill="none"
                  stroke="var(--muted)"
                  strokeWidth="15"
                />
                <circle
                  cx={centerX}
                  cy={centerY}
                  r={radius}
                  fill="none"
                  stroke="var(--color-pass)"
                  strokeWidth="15"
                  strokeLinecap="round"
                  strokeDasharray={`${progress} ${circumference - progress}`}
                  transform={`rotate(-90 ${centerX} ${centerY})`}
                />
                <text
                  x={centerX}
                  y={centerY - 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="var(--foreground)"
                  fontSize="19"
                  fontWeight="600"
                >
                  {row.Reportable}/{row.Enabled}
                </text>
                <text
                  x={centerX}
                  y={centerY + 19}
                  textAnchor="middle"
                  fill="var(--muted-foreground)"
                  fontSize="10.5"
                >
                  {row.percentage}% reportable
                </text>
                <text
                  x={centerX}
                  y="190"
                  textAnchor="middle"
                  fill="var(--muted-foreground)"
                  fontSize="10"
                >
                  {enabledOnly} enabled only
                </text>
              </g>
            )
          })}
          <g transform="translate(398 239)">
            <circle cx="0" cy="0" r="5" fill="var(--color-pass)" />
            <text x="10" y="3.5" fill="var(--muted-foreground)" fontSize="10">Reportable</text>
            <circle cx="128" cy="0" r="5" fill="var(--muted)" />
            <text x="138" y="3.5" fill="var(--muted-foreground)" fontSize="10">Enabled, not reportable</text>
          </g>
        </svg>
      </div>
    </ChartPanel>
  )
}

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
                <div className="h-3 w-full overflow-hidden rounded-full bg-muted" title={tierSummary}>
                  <div className="flex h-full overflow-hidden rounded-full" style={{ width }}>
                    {tiers.map((count, tierIndex) => count > 0 && (
                      <span
                        key={tierIndex}
                        className="h-full min-w-px"
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
