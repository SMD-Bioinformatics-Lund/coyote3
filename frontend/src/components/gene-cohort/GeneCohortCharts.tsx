import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartPanel } from "@/components/plots/ChartPanel"

type Breakdown = {
  profiled_samples: number
  finding_samples: number
  prevalence_percent: number | null
}

type AssayBreakdown = Breakdown & {
  asp_id: string
  display_name: string
  asp_group?: string
}

type SexBreakdown = Breakdown & {
  sex: string
}

type RecurrentFinding = {
  identity: string
  analysis_type: string
  hgvsp?: string
  hgvsc?: string
  sample_count: number
  observation_count: number
  tiers: number[]
}

const tooltipStyle = {
  borderRadius: "8px",
  border: "1px solid var(--border)",
  background: "var(--popover)",
  color: "var(--popover-foreground)",
}

function sexLabel(value: string) {
  if (value === "not_recorded") return "Not recorded"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function GeneCohortCharts({
  gene,
  includeHistory,
  assays,
  tierCounts,
  analysisTypeCounts,
  sexDistribution,
  recurrentFindings,
}: {
  gene: string
  includeHistory: boolean
  assays: AssayBreakdown[]
  tierCounts: Record<string, number>
  analysisTypeCounts: Record<string, number>
  sexDistribution: SexBreakdown[]
  recurrentFindings: RecurrentFinding[]
}) {
  const reportScope = includeHistory ? "historical_reports" : "latest_reports"
  const filenamePrefix = `${gene.toLowerCase()}_${reportScope}`
  const assayData = assays.map((row) => ({
    assay: row.display_name,
    assay_id: row.asp_id,
    assay_group: row.asp_group || "",
    prevalence_percent: row.prevalence_percent,
    finding_samples: row.finding_samples,
    profiled_samples: row.profiled_samples,
  }))
  const tierData = [1, 2, 3, 4].map((tier) => ({
    tier: `Tier ${tier}`,
    observations: tierCounts[String(tier)] || 0,
  }))
  const sexData = sexDistribution.map((row) => ({
    sex: sexLabel(row.sex),
    prevalence_percent: row.prevalence_percent,
    finding_samples: row.finding_samples,
    profiled_samples: row.profiled_samples,
  }))
  const analysisTypeData = Object.entries(analysisTypeCounts).map(([analysis_type, observations]) => ({
    analysis_type,
    observations,
  }))
  const recurrentData = recurrentFindings.slice(0, 10).map((row) => ({
    finding: row.identity,
    analysis_type: row.analysis_type,
    affected_samples: row.sample_count,
    observations: row.observation_count,
    tiers: row.tiers.join(" | "),
  }))
  const tierColors = [
    "var(--color-tier1)",
    "var(--color-tier2)",
    "var(--color-tier3)",
    "var(--color-tier4)",
  ]

  return (
    <section aria-labelledby="cohort-visual-summary-heading" className="surface-panel p-4">
      <div className="surface-panel-heading">
        <h2 id="cohort-visual-summary-heading" className="text-base font-semibold">Cohort visual summary</h2>
        <p className="type-caption text-muted-foreground">
          Prevalence and reported clinical finding patterns for {gene}. Download controls export each plot or its underlying rows.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="h-[22rem] min-w-0">
          <ChartPanel
            title="Prevalence by assay"
            description="Percentage of profiled samples with a reported finding."
            filename={`${filenamePrefix}_assay_prevalence`}
            data={assayData}
          >
            {assayData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={assayData} layout="vertical" margin={{ top: 8, right: 24, left: 16, bottom: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" opacity={0.55} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                  <YAxis type="category" dataKey="assay" width={132} tick={{ fontSize: 10, fill: "var(--foreground)" }} />
                  <Tooltip cursor={{ fill: "var(--chart-tooltip-cursor)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="prevalence_percent" name="Prevalence" fill="var(--color-panel)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="type-body grid h-full place-items-center text-muted-foreground">No assay prevalence is available.</p>}
          </ChartPanel>
        </div>

        <div className="h-[22rem] min-w-0">
          <ChartPanel
            title="Reported tier composition"
            description="Distribution of deduplicated reported finding observations."
            filename={`${filenamePrefix}_tier_distribution`}
            data={tierData}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={tierData} dataKey="observations" nameKey="tier" innerRadius={54} outerRadius={92} paddingAngle={3}>
                  {tierData.map((row, index) => <Cell key={row.tier} fill={tierColors[index]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </ChartPanel>
        </div>

        <div className="h-[22rem] min-w-0">
          <ChartPanel
            title="Prevalence by recorded sex"
            description="Finding prevalence within each recorded sample-sex group."
            filename={`${filenamePrefix}_sex_prevalence`}
            data={sexData}
          >
            {sexData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sexData} margin={{ top: 8, right: 18, left: 0, bottom: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" opacity={0.55} vertical={false} />
                  <XAxis dataKey="sex" tick={{ fontSize: 10, fill: "var(--foreground)" }} />
                  <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                  <Tooltip cursor={{ fill: "var(--chart-tooltip-cursor)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="prevalence_percent" name="Prevalence" fill="var(--color-pass)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="type-body grid h-full place-items-center text-muted-foreground">No sex information is available.</p>}
          </ChartPanel>
        </div>

        <div className="h-[22rem] min-w-0">
          <ChartPanel
            title="Top recurrent findings"
            description="Up to ten typed finding identities ranked by affected samples."
            filename={`${filenamePrefix}_recurrent_findings`}
            data={recurrentData}
          >
            {recurrentData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={recurrentData} layout="vertical" margin={{ top: 8, right: 18, left: 18, bottom: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" opacity={0.55} horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                  <YAxis type="category" dataKey="finding" width={126} tick={{ fontSize: 10, fill: "var(--foreground)" }} />
                  <Tooltip cursor={{ fill: "var(--chart-tooltip-cursor)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="affected_samples" name="Affected samples" fill="var(--color-germline)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="type-body grid h-full place-items-center text-muted-foreground">No recurrent findings are available.</p>}
          </ChartPanel>
        </div>

        <div className="h-[22rem] min-w-0 xl:col-span-2">
          <ChartPanel
            title="Findings by analysis type"
            description="Deduplicated reported observations grouped as SNV, CNV, fusion, or translocation."
            filename={`${filenamePrefix}_analysis_types`}
            data={analysisTypeData}
          >
            {analysisTypeData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analysisTypeData} margin={{ top: 8, right: 18, left: 0, bottom: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" opacity={0.55} vertical={false} />
                  <XAxis dataKey="analysis_type" tick={{ fontSize: 10, fill: "var(--foreground)" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
                  <Tooltip cursor={{ fill: "var(--chart-tooltip-cursor)" }} contentStyle={tooltipStyle} />
                  <Bar dataKey="observations" name="Reported observations" fill="var(--color-panel)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="type-body grid h-full place-items-center text-muted-foreground">No finding types are available.</p>}
          </ChartPanel>
        </div>
      </div>
    </section>
  )
}
