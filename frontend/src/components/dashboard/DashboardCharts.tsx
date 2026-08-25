import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LabelList } from "recharts"
import { ChartPanel } from "@/components/plots/ChartPanel"
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

function CompositionDonut({ group, colors, colorOffset }: { group: CompositionGroup; colors: string[]; colorOffset: number }) {
  const rows = group.rows.filter((row) => row.value > 0)
  const total = rows.reduce((sum, row) => sum + row.value, 0)

  return (
    <figure className="min-w-0 border-b border-border/60 pb-3 last:border-b-0 md:border-b-0 md:border-r md:pr-3 md:last:border-r-0">
      <figcaption className="type-label mb-1.5 text-muted-foreground">{group.name}</figcaption>
      {rows.length ? (
        <div className="grid min-w-0 grid-cols-[7rem_minmax(0,1fr)] items-center gap-2">
          <div className="relative h-28 w-28">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={rows}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={31}
                  outerRadius={49}
                  paddingAngle={3}
                  stroke="none"
                  isAnimationActive={false}
                >
                  {rows.map((row, index) => (
                    <Cell key={row.name} fill={colors[(colorOffset + index) % colors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [shortCount(value), String(name)]}
                  contentStyle={{ borderRadius: "8px", border: "1px solid var(--border)", fontSize: 11 }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <strong className="text-sm font-semibold text-foreground">{shortCount(total)}</strong>
              <span className="text-[9px] uppercase text-muted-foreground">samples</span>
            </div>
          </div>
          <ul className="min-w-0 space-y-1.5">
            {rows.map((row, index) => (
              <li key={row.name} className="flex min-w-0 items-center gap-1.5 text-[11px]">
                <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: colors[(colorOffset + index) % colors.length] }} />
                <span className="min-w-0 flex-1 truncate capitalize text-muted-foreground">{row.name || "unknown"}</span>
                <strong className="shrink-0 font-semibold text-foreground">{shortCount(row.value)}</strong>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="flex h-28 items-center justify-center text-xs text-muted-foreground">No data</div>
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
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
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
              innerRadius="42%"
              outerRadius="70%"
              paddingAngle={4}
            >
              {data.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ borderRadius: "10px", border: "1px solid var(--color-border)" }} />
            <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 11, lineHeight: "18px" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  )
}

export function GeneCoverageChart({
  data,
}: {
  data: Array<{ name: string; Covered: number; Germline: number }>
}) {
  return (
    <ChartPanel
      title="Gene coverage per assay"
      description="Covered and germline gene scope from active ASP definitions."
      filename="gene_coverage_per_assay"
      data={data}
    >
      <div className="h-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 64 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.22} />
            <XAxis dataKey="name" angle={-30} textAnchor="end" height={72} tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip cursor={{ fill: "var(--chart-tooltip-cursor)" }} contentStyle={{ borderRadius: "10px", border: "1px solid var(--border)" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="Covered" fill="var(--color-panel)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Germline" fill="var(--color-germline)" radius={[4, 4, 0, 0]} />
          </BarChart>
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
      summary: `${reportable} / ${enabled}  ${percentage}%`,
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
        className="h-full min-h-0"
        role="img"
        aria-label={`Panel analysis capability. ${accessibleSummary}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 104, left: 8, bottom: 4 }}
            barCategoryGap="34%"
          >
            <CartesianGrid strokeDasharray="3 3" opacity={0.16} horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
            <Tooltip
              formatter={(value, name) => {
                if (name === "Enabled only") return [value, "Enabled, not reportable"]
                return [value, String(name)]
              }}
              labelFormatter={(name, payload) => {
                const row = payload?.[0]?.payload as (typeof rows)[number] | undefined
                return row ? `${name} · ${row.summary}` : String(name)
              }}
              cursor={{ fill: "var(--chart-tooltip-cursor)" }}
              contentStyle={{ borderRadius: "10px", border: "1px solid var(--border)", fontSize: 11 }}
            />
            <Legend
              verticalAlign="bottom"
              formatter={(value) => value === "Enabled only" ? "Enabled, not reportable" : value}
              wrapperStyle={{ fontSize: 11, lineHeight: "18px" }}
            />
            <Bar dataKey="Reportable" stackId="capability" fill="var(--color-pass)" radius={[5, 0, 0, 5]} isAnimationActive={false} />
            <Bar dataKey="Enabled only" stackId="capability" fill="var(--color-panel)" radius={[0, 5, 5, 0]} isAnimationActive={false}>
              <LabelList dataKey="summary" position="right" offset={10} fill="var(--foreground)" fontSize={10} fontWeight={600} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  )
}
