import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"
import { shortCount } from "@/lib/detail-formatters"
import { donutTooltipLayer } from "@/components/plots/chart-options"
import type { ChartProps, CompositionItem } from "@/components/plots/chart-data"

type CompositionGroup = { name: string; rows: CompositionItem[] }
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
    <figure className="dashboard-subcard min-w-0 p-3">
      <figcaption className="type-body-sm mb-3 font-semibold text-foreground">{group.name}</figcaption>
      {rows.length ? (
        <div className="grid min-w-0 grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-3">
          <div
            className="relative h-26 w-26"
            role="img"
            aria-label={`${group.name}: ${rows.map((row) => `${row.name} ${row.value} of ${total}`).join(", ")}`}
          >
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
                  outerRadius={47}
                  paddingAngle={rows.length > 1 ? 3 : 0}
                  cornerRadius={2}
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
                  wrapperStyle={donutTooltipLayer}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <strong className="type-section-title tabular-nums text-foreground">{shortCount(total)}</strong>
              <span className="type-meta text-muted-foreground">{total === 1 ? "sample" : "samples"}</span>
            </div>
          </div>
          <ul className="min-w-0 space-y-1.5">
            {rows.map((row, index) => (
              <li key={row.name} className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-0.5 type-body-sm">
                <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full" style={{ background: colors[(colorOffset + index) % colors.length] }} />
                <span className="min-w-0 capitalize text-foreground">{/^(dna|rna)$/i.test(row.name) ? row.name.toUpperCase() : row.name || "Unknown"}</span>
                <strong className="font-semibold tabular-nums text-foreground">{shortCount(row.value)}</strong>
                <span className="col-start-2 col-span-2 type-meta tabular-nums text-muted-foreground">{Math.round(row.value / total * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="flex h-26 items-center justify-center type-body-sm text-muted-foreground">No data</div>
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
  const maximumPipelineCount = Math.max(1, ...visiblePipelines.map((pipeline) => pipeline.Total))

  return (
    <div className="sample-composition space-y-4">
      <div className="sample-composition-grid">
        {groups.map((group, index) => (
          <CompositionDonut key={group.name} group={group} colors={colors} colorOffset={index * 2} />
        ))}
      </div>

      <div className="border-t border-border/70 pt-3">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="type-section-title text-foreground">Pipeline throughput</h3>
            <p className="type-body-sm mt-0.5 text-muted-foreground">Analysis completion by pipeline and version.</p>
          </div>
          <div className="flex items-center gap-3 type-meta text-muted-foreground">
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-pass" />Analysed</span>
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-warning" />Awaiting review</span>
          </div>
        </div>
        {visiblePipelines.length ? (
          <div
            role="img"
            aria-label={`Pipeline throughput. ${pipelineSummary}`}
            className="space-y-4 pt-2"
          >
            {visiblePipelines.map((pipeline) => (
              <div key={pipeline.label} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3 type-body-sm">
                  <span className="min-w-0 font-medium text-foreground">{pipeline.label}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">{shortCount(pipeline.Total)} {pipeline.Total === 1 ? "sample" : "samples"}</span>
                </div>
                <div className="progress-pipe flex h-2.5 overflow-hidden rounded-full" aria-hidden="true">
                  <span className="progress-pipe-segment bg-pass" style={{ width: `${pipeline.Analysed / maximumPipelineCount * 100}%` }} />
                  <span className="progress-pipe-segment bg-warning" style={{ width: `${pipeline["Awaiting review"] / maximumPipelineCount * 100}%` }} />
                </div>
                <div className="flex flex-wrap justify-between gap-x-3 gap-y-1 type-meta tabular-nums text-muted-foreground">
                  <span>{shortCount(pipeline.Analysed)} analysed · {shortCount(pipeline["Awaiting review"])} awaiting review</span>
                  <span>{pipeline.Total ? Math.round(pipeline.Analysed / pipeline.Total * 100) : 0}% complete</span>
                </div>
              </div>
            ))}
            <p className="type-meta text-muted-foreground">Shared count scale: 0–{shortCount(maximumPipelineCount)} samples</p>
          </div>
        ) : (
          <p className="py-4 type-body-sm text-muted-foreground">No pipeline data available.</p>
        )}
      </div>
    </div>
  )
}
