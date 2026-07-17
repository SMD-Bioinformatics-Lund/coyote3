import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Suspense, lazy } from "react"
import { api } from "@/lib/api"
import { Activity, AlertTriangle } from "lucide-react"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { shortCount } from "@/lib/detail-formatters"

const chartColors = ["var(--color-tier1)", "var(--color-tier2)", "var(--color-tier3)", "var(--color-tier4)", "var(--color-dna)", "var(--color-rna)", "var(--color-panel)"]
const TierDistributionChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.TierDistributionChart })))
const GeneCoverageChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.GeneCoverageChart })))

function fmt(value: unknown) {
  return shortCount(value)
}

function Metric({ title, value, sub }: { title: string; value: unknown; sub?: string }) {
  return (
    <MetricCard title={title} value={fmt(value)} sub={sub} />
  )
}

function ChartFallback() {
  return (
    <div className="flex h-full items-center justify-center rounded-lg bg-muted/40 text-xs font-semibold text-muted-foreground">
      Loading chart...
    </div>
  )
}

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get("/dashboard/summary").then((res) => res.data?.payload || res.data),
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <Activity className="h-8 w-8 animate-spin" />
          <p>Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertTriangle className="mr-2 inline h-4 w-4" />
        {error instanceof Error ? error.message : "Failed to load dashboard"}
      </div>
    )
  }

  const vStats = data?.variant_stats || {}
  const uStats = data?.user_samples_stats || {}
  const sStats = data?.sample_stats || {}
  const tierStats = data?.tier_stats?.total || data?.tier_stats || {}
  const quality = data?.quality_stats || {}
  const capacity = data?.capacity_counts || {}
  const geneGroups = data?.assay_gene_stats_grouped || {}

  const geneChartData = Object.keys(geneGroups).flatMap(group =>
    (geneGroups[group] || []).map((assay: any) => ({
      name: assay.display_name || assay.assay_name,
      Covered: assay.covered_genes_count || 0,
      Germline: assay.germline_genes_count || 0,
    }))
  )

  const tierChartData = [1, 2, 3, 4].map((tier) => ({
    name: `Tier ${tier}`,
    value: Number(tierStats[`tier${tier}`] || 0),
  })).filter((item) => item.value > 0)

  const profileData = Object.entries(sStats.profiles || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const capacityEntries = Object.entries(capacity)

  return (
    <div className="max-w-[2600px] space-y-3">
      <div className="surface-panel flex flex-col gap-3 p-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-primary">Operations</p>
          <h1 className="text-2xl font-black tracking-tight">Dashboard</h1>
          <p className="mt-1 text-xs text-muted-foreground">Throughput, quality, tiering, assay scope, and resource health.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/samples" className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-primary-foreground shadow-sm">Open samples</Link>
          <Link to="/variants/search" className="rounded-lg border border-border bg-background px-3 py-2 text-xs font-bold hover:bg-muted">Variant search</Link>
          <Link to="/catalog" className="rounded-lg border border-border bg-background px-3 py-2 text-xs font-bold hover:bg-muted">Catalog</Link>
        </div>
      </div>

      <SurfacePanel title="Operational Snapshot" description="Current sample throughput and total variant volume.">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Metric title="Total samples" value={data?.total_samples} sub="All records" />
          <Metric title="Analysed" value={data?.analysed_samples} sub="Completed workflows" />
          <Metric title="Pending" value={data?.pending_samples} sub="Awaiting review" />
          <Metric title="Variants" value={vStats.total_variants} sub={`${fmt(vStats.unique_variants)} unique`} />
        </div>
      </SurfacePanel>

      <div className="grid gap-3 xl:grid-cols-[1.05fr_0.95fr]">
        <SurfacePanel title="Review Workload" description="Assay progress and profile distribution.">
          <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="grid gap-2 sm:grid-cols-2">
            {Object.keys(uStats).length === 0 ? (
              <p className="text-xs text-muted-foreground">No progress data available.</p>
            ) : Object.keys(uStats).map((assay) => {
              const stats = uStats[assay]
              const percent = stats.total > 0 ? (stats.analysed / stats.total) * 100 : 0
              return (
                <div key={assay} className="rounded-lg border border-border bg-background/70 p-2.5">
                  <div className="mb-2 flex justify-between">
                    <h3 className="text-[11px] font-bold uppercase">{assay}</h3>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">{stats.analysed}/{stats.total}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-gradient-to-r from-dna to-rna" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-2 text-right text-[11px] text-muted-foreground">Pending {stats.pending}</p>
                </div>
              )
            })}
            </div>

            <div className="space-y-2">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Sample Profiles</h3>
              {profileData.length ? profileData.map((item, index) => (
                <div key={item.name} className="rounded-lg border border-border bg-background/60 p-2">
                  <div className="flex justify-between text-[11px] font-bold uppercase">
                    <span>{item.name}</span>
                    <span>{fmt(item.value)}</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, (item.value / Math.max(...profileData.map(p => p.value), 1)) * 100)}%`, background: chartColors[index % chartColors.length] }} />
                  </div>
                </div>
              )) : <p className="text-xs text-muted-foreground">No profile data.</p>}
            </div>
          </div>
        </SurfacePanel>

        <SurfacePanel title="Variant Review" description="Finding counts and classification quality indicators.">
          <div className="grid gap-3 lg:grid-cols-[1fr_15rem]">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Metric title="SNV" value={vStats.snv} />
              <Metric title="CNV" value={vStats.cnvs || vStats.cnv} />
              <Metric title="Fusions" value={vStats.fusions} />
              <Metric title="Translocations" value={vStats.sv || vStats.translocations} />
              <Metric title="Blacklisted" value={vStats.blacklisted} sub={`${quality.blacklist_rate_percent ?? 0}%`} />
              <Metric title="False positives" value={vStats.fps} sub={`${quality.false_positive_rate_percent ?? 0}%`} />
              <Metric title="Pathogenic" value={vStats.pathogenic} />
              <Metric title="VUS" value={vStats.vus} />
            </div>
            <div className="min-h-48 rounded-lg border border-border bg-background/60 p-2">
              <h3 className="mb-1 text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Tier Distribution</h3>
              {tierChartData.length ? (
                <div className="h-44">
                  <Suspense fallback={<ChartFallback />}>
                    <TierDistributionChart data={tierChartData} colors={chartColors} />
                  </Suspense>
                </div>
              ) : <p className="text-xs text-muted-foreground">No tier data available.</p>}
            </div>
          </div>
        </SurfacePanel>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <SurfacePanel title="Gene Coverage Per Assay" description="Covered and germline gene scope across assays.">
          <div className="h-[320px]">
            <Suspense fallback={<ChartFallback />}>
              <GeneCoverageChart data={geneChartData} />
            </Suspense>
          </div>
        </SurfacePanel>

        <SurfacePanel title="Resource Capacity" description="Configured resources and reference inventory.">
          <div className="grid grid-cols-2 gap-2">
            {capacityEntries.length ? capacityEntries.map(([key, value], index) => (
              <div key={key} className="rounded-lg border border-border bg-background/70 p-2.5">
                <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="mt-1 text-base font-black" style={{ color: chartColors[index % chartColors.length] }}>{fmt(value)}</p>
              </div>
            )) : <p className="text-xs text-muted-foreground">No capacity data available.</p>}
          </div>
        </SurfacePanel>
      </div>
    </div>
  )
}
