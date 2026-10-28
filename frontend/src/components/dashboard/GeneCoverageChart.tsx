import { XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ScatterChart, Scatter } from "recharts"
import { ChartPanel } from "@/components/plots/ChartPanel"
import { shortCount } from "@/lib/detail-formatters"

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
      description="Covered and germline gene scope from active assay definitions."
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
