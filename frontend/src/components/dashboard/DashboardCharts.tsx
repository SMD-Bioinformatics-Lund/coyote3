import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"
import { ChartPanel } from "@/components/plots/ChartPanel"

type ChartProps = {
  colors: string[]
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
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={34} outerRadius={62} paddingAngle={3}>
              {data.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ borderRadius: "10px", border: "1px solid var(--color-border)" }} />
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
