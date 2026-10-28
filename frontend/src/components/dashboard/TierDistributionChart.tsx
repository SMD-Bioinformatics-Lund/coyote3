import { Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"
import { ChartPanel } from "@/components/plots/ChartPanel"
import { donutMotion, donutTooltipLayer } from "@/components/plots/chart-options"
import type { ChartProps } from "@/components/plots/chart-data"

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
