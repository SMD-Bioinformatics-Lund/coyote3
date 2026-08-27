import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, ScatterChart, Scatter } from "recharts"
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
          viewBox="0 0 1120 210"
          className="h-full min-h-[190px] w-full min-w-[840px]"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          {rows.map((row, index) => {
            const cellWidth = 1120 / Math.max(rows.length, 1)
            const centerX = cellWidth * index + cellWidth / 2
            const centerY = 88
            const radius = 46
            const circumference = 2 * Math.PI * radius
            const progress = circumference * (row.percentage / 100)
            const enabledOnly = row["Enabled only"]

            return (
              <g key={row.name}>
                <title>{`${row.name}: ${row.Reportable} reportable of ${row.Enabled} enabled (${row.percentage}%). ${enabledOnly} enabled but not reportable.`}</title>
                <text
                  x={centerX}
                  y="17"
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
                  strokeWidth="13"
                />
                <circle
                  cx={centerX}
                  cy={centerY}
                  r={radius}
                  fill="none"
                  stroke="var(--color-pass)"
                  strokeWidth="13"
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
                  fontSize="17"
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
                  y="158"
                  textAnchor="middle"
                  fill="var(--muted-foreground)"
                  fontSize="10"
                >
                  {enabledOnly} enabled only
                </text>
              </g>
            )
          })}
          <g transform="translate(398 195)">
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
