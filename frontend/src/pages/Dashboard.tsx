import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Suspense, lazy } from "react"
import { api } from "@/lib/api"
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock, Users } from "lucide-react"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { humanRelativeDate, localDate, shortCount } from "@/lib/detail-formatters"
import { sampleDetailPath } from "@/lib/sample-routing"

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

function percent(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(numeric % 1 === 0 ? 0 : 1)}%` : "0%"
}

function miniBarWidth(value: number, values: number[]) {
  return `${Math.min(100, (value / Math.max(...values, 1)) * 100)}%`
}

function humanDate(value: unknown) {
  const relative = humanRelativeDate(value, "")
  if (relative && !relative.includes("mo ") && !relative.includes("yr ")) return relative
  return localDate(value)
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
    return <AppLoader label="Loading dashboard" />
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
  const isglVisibility = data?.isgl_visibility || {}
  const isglAssociationRows = data?.isgl_association?.assay_isgl_counts || []
  const userScope = data?.user_scope_summary || {}
  const scopeStats = userScope.sample_stats || {}
  const recentSamples = userScope.recent_samples || []

  const geneChartData = Object.keys(geneGroups).flatMap(group =>
    (geneGroups[group] || []).map((assay: any) => ({
      name: assay.display_name || assay.assay_name,
      Covered: Number(assay.covered_genes_count ?? assay.gene_count ?? 0),
      Germline: Number(assay.germline_genes_count ?? assay.germline_gene_count ?? 0),
    }))
  )
  const hasGeneChartData = geneChartData.some((item) => item.Covered > 0 || item.Germline > 0)

  const tierChartData = [1, 2, 3, 4].map((tier) => ({
    name: `Tier ${tier}`,
    value: Number(tierStats[`tier${tier}`] || 0),
  })).filter((item) => item.value > 0)
  const findingTotal = Number(vStats.snv || 0) + Number(vStats.cnv || vStats.cnvs || 0) + Number(vStats.fusion || vStats.fusions || 0) + Number(vStats.translocation || vStats.translocations || 0)

  const profileData = Object.entries(sStats.profiles || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const statusData = Object.entries(sStats.ingest_statuses || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const omicsData = Object.entries(sStats.omics_layers || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const scopeData = Object.entries(sStats.sequencing_scopes || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const pairingData = Object.entries(sStats.pair_count || {}).map(([name, value]) => ({ name, value: Number(value) }))
  const variantClassData = Object.entries(vStats.by_variant_class || {}).map(([name, value]) => ({ name, value: Number(value) })).sort((a, b) => b.value - a.value)
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
          <Link to="/public/catalog" className="rounded-lg border border-border bg-background px-3 py-2 text-xs font-bold hover:bg-muted">Catalog</Link>
        </div>
      </div>

      <SurfacePanel title="Operational Snapshot" description="Current sample throughput and total variant volume.">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Metric title="My visible samples" value={userScope.total_samples ?? data?.total_samples} sub={`${percent(userScope.analysed_rate_percent ?? quality.analysed_rate_percent)} analysed`} />
          <Metric title="My pending review" value={userScope.pending_samples ?? data?.pending_samples} sub="Visible from my roles and assays" />
          <Metric title="All samples" value={data?.total_samples} sub={`${fmt(data?.analysed_samples)} analysed`} />
          <Metric title="Findings" value={findingTotal} sub={`${fmt(vStats.unique_variants)} unique small variants`} />
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

        <SurfacePanel title="My Recent Samples" description="Latest samples visible to your account.">
          <div className="space-y-2">
            {recentSamples.length ? recentSamples.map((sample: any) => (
              <Link key={sample.id || sample.name} to={sampleDetailPath(sample, sample.id)} className="group flex items-center justify-between gap-3 rounded-lg border border-border bg-background/70 p-2.5 hover:border-primary/40 hover:bg-primary/5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-black text-primary">{sample.name || sample.id}</p>
                    <span className="rounded-md bg-dna/10 px-1.5 py-0.5 text-[10px] font-bold uppercase text-dna">{sample.omics_layer || "dna"}</span>
                    <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-bold uppercase text-muted-foreground">{sample.ingest_status || "unknown"}</span>
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {sample.assay || "-"} {sample.subpanel_id || sample.subpanel ? `• ${sample.subpanel_id || sample.subpanel}` : ""} • {humanDate(sample.time_added)}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </Link>
            )) : <p className="text-xs text-muted-foreground">No recent visible samples.</p>}
          </div>
        </SurfacePanel>
      </div>

      <div className="grid gap-3 xl:grid-cols-[0.8fr_1.2fr]">
        <SurfacePanel title="Sample Composition" description="Profiles, status, modality, and sequencing scope.">
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ["Ingest status", statusData, CheckCircle2],
              ["Omics", omicsData, Activity],
              ["Sequencing scope", scopeData, Users],
              ["My profile scope", Object.entries(scopeStats.profiles || {}).map(([name, value]) => ({ name, value: Number(value) })), Clock],
              ["Pairing", pairingData, Users],
            ].map(([title, rows, Icon]: any, panelIndex) => (
              <div key={title} className="rounded-lg border border-border bg-background/70 p-2.5">
                <div className="mb-2 flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" />
                  <h3 className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">{title}</h3>
                </div>
                <div className="space-y-1.5">
                  {rows.length ? rows.map((item: any, index: number) => (
                    <div key={item.name} className="space-y-1">
                      <div className="flex justify-between gap-3 text-[11px] font-bold uppercase">
                        <span className="truncate">{item.name || "unknown"}</span>
                        <span>{fmt(item.value)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full" style={{ width: miniBarWidth(item.value, rows.map((row: any) => row.value)), background: chartColors[(panelIndex + index) % chartColors.length] }} />
                      </div>
                    </div>
                  )) : <p className="text-xs text-muted-foreground">No data.</p>}
                </div>
              </div>
            ))}
          </div>
        </SurfacePanel>

        <SurfacePanel title="Variant Review" description="Finding counts and classification quality indicators.">
          <div className="grid gap-3 lg:grid-cols-[1fr_15rem_14rem]">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Metric title="Small variants" value={vStats.snv || vStats.small_variants} sub={`${fmt(vStats.snps)} SNV/SNP class`} />
              <Metric title="CNV" value={vStats.cnv || vStats.cnvs} />
              <Metric title="Fusions" value={vStats.fusion || vStats.fusions} />
              <Metric title="Translocations" value={vStats.translocation || vStats.translocations} />
              <Metric title="Blacklisted" value={vStats.blacklisted} sub={`${quality.blacklist_rate_percent ?? 0}%`} />
              <Metric title="False positives" value={vStats.fps || vStats.false_positives} sub={`${quality.fp_rate_percent ?? quality.false_positive_rate_percent ?? 0}%`} />
              <Metric title="Tier 1/2" value={vStats.tier1_or_2 ?? vStats.pathogenic} sub="Report-priority findings" />
              <Metric title="VUS" value={vStats.vus} />
              <Metric title="Reported findings" value={vStats.reported_findings} sub="Saved report snapshots" />
              <Metric title="Tier 4" value={vStats.tier4} sub="Usually not reportable" />
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
            <div className="min-h-48 rounded-lg border border-border bg-background/60 p-2">
              <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Small Variant Classes</h3>
              <div className="space-y-2">
                {variantClassData.length ? variantClassData.slice(0, 6).map((item, index) => (
                  <div key={item.name} className="space-y-1">
                    <div className="flex justify-between gap-3 text-[11px] font-bold uppercase">
                      <span className="truncate">{item.name || "unknown"}</span>
                      <span>{fmt(item.value)}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full" style={{ width: miniBarWidth(item.value, variantClassData.map((row) => row.value)), background: chartColors[index % chartColors.length] }} />
                    </div>
                  </div>
                )) : <p className="text-xs text-muted-foreground">No class data available.</p>}
              </div>
            </div>
          </div>
        </SurfacePanel>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <SurfacePanel title="Gene Coverage Per Assay" description="Covered and germline gene scope across assays.">
          <div className="h-[320px]">
            {hasGeneChartData ? (
              <Suspense fallback={<ChartFallback />}>
                <GeneCoverageChart data={geneChartData} />
              </Suspense>
            ) : (
              <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 text-center">
                <p className="text-sm font-black text-foreground">No active panel gene counts available</p>
                <p className="mt-1 max-w-md text-xs text-muted-foreground">
                  Active ASP documents need populated covered_genes or germline_genes arrays before the coverage chart can be drawn.
                </p>
              </div>
            )}
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

      <SurfacePanel title="Clinical Configuration" description="Gene-list visibility and assay coverage for interpretation workflows.">
        <div className="grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
            <Metric title="Unique active genes" value={data?.unique_gene_count_all_panels} sub="Across active ASPs" />
            <Metric title="Public ISGLs" value={isglVisibility.public_total} sub={`${fmt(isglVisibility.public_only)} public only`} />
            <Metric title="Private ISGLs" value={isglVisibility.private_total} sub={`${fmt(isglVisibility.private_only)} private only`} />
            <Metric title="Ad-hoc lists" value={isglVisibility.adhoc_total} sub={`${fmt(isglVisibility.overlap_total)} overlapping`} />
          </div>
          <div className="rounded-lg border border-border bg-background/70 p-2.5">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Top Assay ISGL Associations</h3>
              <Link to="/public/catalog" className="text-[11px] font-bold text-primary hover:underline">Open catalog</Link>
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {isglAssociationRows.length ? isglAssociationRows.slice(0, 6).map((row: any) => (
                <div key={row.assay_id || row.display_name} className="rounded-lg border border-border bg-muted/20 p-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-black text-foreground">{row.display_name || row.assay_id}</p>
                      <p className="mt-0.5 truncate text-[10px] font-bold uppercase text-muted-foreground">{row.asp_group || "unassigned"}</p>
                    </div>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-black text-primary">{fmt(row.isgl_total)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-bold text-green-700 dark:text-green-300">{fmt(row.public_count)} public</span>
                    <span className="rounded-md bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700 dark:text-indigo-300">{fmt(row.private_count)} private</span>
                    <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-700 dark:text-amber-300">{fmt(row.adhoc_count)} ad-hoc</span>
                  </div>
                </div>
              )) : <p className="text-xs text-muted-foreground">No assay-to-ISGL associations configured.</p>}
            </div>
          </div>
        </div>
      </SurfacePanel>
    </div>
  )
}
