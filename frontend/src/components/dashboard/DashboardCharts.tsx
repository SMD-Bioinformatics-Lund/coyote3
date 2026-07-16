import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts"

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
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={34} outerRadius={62} paddingAngle={3}>
          {data.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function GeneCoverageChart({
  data,
}: {
  data: Array<{ name: string; Covered: number; Germline: number }>
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 64 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.22} />
        <XAxis dataKey="name" angle={-30} textAnchor="end" height={72} tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip cursor={{ fill: "rgba(0,0,0,0.05)" }} contentStyle={{ borderRadius: "10px", border: "1px solid var(--color-border)" }} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="Covered" fill="var(--color-panel)" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Germline" fill="var(--color-germline)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
