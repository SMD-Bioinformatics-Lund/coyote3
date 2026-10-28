import { ChartPanel } from "@/components/plots/ChartPanel"

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
  const canvasWidth = Math.max(360, rows.length * 160)

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
          viewBox={`0 0 ${canvasWidth} 260`}
          className="h-full min-h-[230px] w-full"
          style={{ minWidth: canvasWidth }}
          preserveAspectRatio="xMinYMid meet"
          aria-hidden="true"
        >
          {rows.map((row, index) => {
            const cellWidth = canvasWidth / Math.max(rows.length, 1)
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
                  className="panel-capability-track"
                  stroke="var(--chart-track)"
                  strokeWidth="15"
                />
                {progress > 0 && <circle
                  cx={centerX}
                  cy={centerY}
                  r={radius}
                  fill="none"
                  stroke="var(--color-pass)"
                  className="panel-capability-progress"
                  strokeWidth="15"
                  strokeLinecap="round"
                  strokeDasharray={`${progress} ${circumference - progress}`}
                  transform={`rotate(-90 ${centerX} ${centerY})`}
                />}
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
          <g transform={`translate(${(canvasWidth - 324) / 2} 239)`}>
            <circle cx="0" cy="0" r="5" fill="var(--color-pass)" />
            <text x="10" y="3.5" fill="var(--muted-foreground)" fontSize="10">Reportable</text>
            <circle cx="128" cy="0" r="5" fill="var(--chart-track)" />
            <text x="138" y="3.5" fill="var(--muted-foreground)" fontSize="10">Enabled, not reportable</text>
          </g>
        </svg>
      </div>
    </ChartPanel>
  )
}
