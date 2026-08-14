import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Suspense, lazy } from "react"
import { api } from "@/lib/api"
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock, Users } from "lucide-react"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { buttonVariants } from "@/components/ui/button-variants"
import { humanRelativeDate, localDate, shortCount } from "@/lib/detail-formatters"
import { buildPanelAnalysisCapabilityData, buildPanelGeneChartData } from "@/lib/dashboard-data"
import { sampleDetailPath } from "@/lib/sample-routing"
import { cn } from "@/lib/utils"

const chartColors = ["var(--color-tier1)", "var(--color-tier2)", "var(--color-tier3)", "var(--color-tier4)", "var(--color-dna)", "var(--color-rna)", "var(--color-panel)"]
const TierDistributionChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.TierDistributionChart })))
const GeneCoverageChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.GeneCoverageChart })))
const PanelAnalysisCapabilityChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.PanelAnalysisCapabilityChart })))

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
  const geneGroups = data?.panel_gene_stats_grouped || {}
  const panelPortfolio = data?.panel_portfolio || {}
  const panelAnalysisCapabilityData = buildPanelAnalysisCapabilityData(data?.panel_analysis_capabilities || [])
  const isglVisibility = data?.isgl_visibility || {}
  const isglAssociationRows = data?.isgl_association?.assay_isgl_counts || []
  const userScope = data?.user_scope_summary || {}
  const scopeStats = userScope.sample_stats || {}
  const recentSamples = (userScope.recent_samples || []).slice(0, 5)

  const geneChartData = buildPanelGeneChartData(geneGroups)
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
    <PageShell
      eyebrow="Operations"
      title="Dashboard"
      description="Throughput, quality, tiering, assay scope, and resource health."
      className="space-y-3"
      actions={
        <>
          <Link to="/samples" className={buttonVariants({ size: "sm" })}>Open samples</Link>
          <Link to="/variants/search" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "paper-raised-control")}>Variant search</Link>
          <Link to="/public/catalog" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "paper-raised-control")}>Catalog</Link>
        </>
      }
    >

      <SurfacePanel className="dashboard-panel" title="Operational Snapshot" description="Current clinical workload, analysis progress, and finding volume.">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[1.45fr_1fr_1fr]">
          <div className="dashboard-snapshot-card p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="type-label text-muted-foreground">Analysis progress</p>
                <p className="mt-1 text-xl font-semibold leading-tight text-foreground">
                  {fmt(data?.analysed_samples)} <span className="text-sm font-medium text-muted-foreground">of {fmt(data?.total_samples)} analysed</span>
                </p>
              </div>
              <CheckCircle2 className="mt-0.5 h-5 w-5 text-pass" />
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-pass" style={{ width: `${Math.min(100, Number(data?.total_samples) > 0 ? (Number(data?.analysed_samples || 0) / Number(data?.total_samples)) * 100 : 0)}%` }} />
            </div>
            <div className="type-meta mt-2 flex items-center justify-between text-muted-foreground">
              <span>{percent(userScope.analysed_rate_percent ?? quality.analysed_rate_percent)} complete in your visible scope</span>
              <span className="font-semibold text-foreground">{fmt(userScope.pending_samples ?? data?.pending_samples)} awaiting review</span>
            </div>
          </div>
          <div className="dashboard-snapshot-card p-3">
            <p className="type-label text-muted-foreground">My visible samples</p>
            <p className="mt-1 text-xl font-semibold leading-tight text-foreground">{fmt(userScope.total_samples ?? data?.total_samples)}</p>
            <p className="type-meta mt-2 text-muted-foreground">Available through your roles, assays, and environments.</p>
          </div>
          <div className="dashboard-snapshot-card p-3">
            <p className="type-label text-muted-foreground">Finding inventory</p>
            <p className="mt-1 text-xl font-semibold leading-tight text-foreground">{fmt(findingTotal)}</p>
            <p className="type-meta mt-2 text-muted-foreground">{fmt(vStats.unique_variants)} unique small variants across visible samples.</p>
          </div>
        </div>
      </SurfacePanel>

      <div className="grid items-stretch gap-3 xl:grid-cols-[1.05fr_0.95fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--teal h-full" title="Review Workload" description="Assay progress and profile distribution.">
          <div className="flex h-full flex-col gap-3">
          <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="grid gap-2 sm:grid-cols-2">
            {Object.keys(uStats).length === 0 ? (
              <p className="text-xs text-muted-foreground">No progress data available.</p>
            ) : Object.keys(uStats).map((assay) => {
              const stats = uStats[assay]
              const percent = stats.total > 0 ? (stats.analysed / stats.total) * 100 : 0
              return (
                <div key={assay} className="dashboard-subcard p-2.5">
                  <div className="mb-2 flex justify-between">
                    <h3 className="type-label">{assay}</h3>
                    <span className="type-badge rounded-full bg-primary/10 px-2 py-0.5 text-primary">{stats.analysed}/{stats.total}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary/80" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="type-meta mt-2 text-right text-muted-foreground">Pending {stats.pending}</p>
                </div>
              )
            })}
            </div>

            <div className="space-y-2">
              <h3 className="type-label text-muted-foreground">Sample Profiles</h3>
              {profileData.length ? profileData.map((item, index) => (
                <div key={item.name} className="dashboard-subcard p-2">
                  <div className="type-meta flex justify-between uppercase">
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
          <div className="dashboard-workload-summary mt-auto grid gap-2 sm:grid-cols-3">
            <div><span>Visible</span><strong>{fmt(userScope.total_samples ?? data?.total_samples)}</strong></div>
            <div><span>Pending review</span><strong>{fmt(userScope.pending_samples ?? data?.pending_samples)}</strong></div>
            <div><span>Analysed</span><strong>{fmt(data?.analysed_samples)}</strong></div>
          </div>
          </div>
        </SurfacePanel>

        <SurfacePanel className="dashboard-panel dashboard-panel--rose h-full" title="My Recent Samples" description="Latest samples visible to your account.">
          <div className="space-y-2">
            {recentSamples.length ? recentSamples.map((sample: any) => (
              <Link key={sample.id || sample.name} to={sampleDetailPath(sample, sample.id)} className="dashboard-subcard group flex items-center justify-between gap-3 p-2.5 hover:border-primary/40 hover:bg-primary/5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-primary">{sample.name || sample.id}</p>
                    <span className="type-badge rounded-md bg-dna/10 px-1.5 py-0.5 uppercase text-dna">{sample.omics_layer || "dna"}</span>
                    <span className="type-badge rounded-md bg-muted px-1.5 py-0.5 uppercase text-muted-foreground">{sample.ingest_status || "unknown"}</span>
                  </div>
                  <p className="type-meta mt-0.5 truncate text-muted-foreground">
                    {sample.asp_id || "-"} {sample.subpanel_id ? `• ${sample.subpanel_id}` : ""} • {humanDate(sample.time_added)}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </Link>
            )) : <p className="text-xs text-muted-foreground">No recent visible samples.</p>}
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-xs text-muted-foreground">
            <span>Showing up to 5 most recent samples.</span>
            <Link to="/samples" className="inline-flex items-center gap-1 font-semibold text-link hover:underline">
              View all samples
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </SurfacePanel>
      </div>

      <div className="grid items-start gap-3 xl:grid-cols-[0.8fr_1.2fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--amber" title="Sample Composition" description="Profiles, status, modality, and sequencing scope.">
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ["Ingest status", statusData, CheckCircle2],
              ["Omics", omicsData, Activity],
              ["Sequencing scope", scopeData, Users],
              ["My profile scope", Object.entries(scopeStats.profiles || {}).map(([name, value]) => ({ name, value: Number(value) })), Clock],
              ["Pairing", pairingData, Users],
            ].map(([title, rows, Icon]: any, panelIndex) => (
              <div key={title} className="dashboard-subcard p-2.5">
                <div className="mb-2 flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" />
                  <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
                </div>
                <div className="space-y-1.5">
                  {rows.length ? rows.map((item: any, index: number) => (
                    <div key={item.name} className="space-y-1">
                      <div className="flex justify-between gap-3 text-[11px] font-medium uppercase">
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

        <SurfacePanel className="dashboard-panel dashboard-panel--blue" title="Variant Review" description="Finding counts and classification quality indicators.">
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
            <div className="dashboard-subcard min-h-48 p-2">
              <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tier Distribution</h3>
              {tierChartData.length ? (
                <div className="h-44">
                  <Suspense fallback={<ChartFallback />}>
                    <TierDistributionChart data={tierChartData} colors={chartColors} />
                  </Suspense>
                </div>
              ) : <p className="text-xs text-muted-foreground">No tier data available.</p>}
            </div>
            <div className="dashboard-subcard min-h-48 p-2">
              <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Small Variant Classes</h3>
              <div className="space-y-2">
                {variantClassData.length ? variantClassData.slice(0, 6).map((item, index) => (
                  <div key={item.name} className="space-y-1">
                    <div className="flex justify-between gap-3 text-[11px] font-medium uppercase">
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

      <div className="grid items-stretch gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--teal h-full" title="Panel Gene Coverage" description="Covered and germline gene scope across active targeted panels.">
          <div className="h-[320px]">
            {hasGeneChartData ? (
              <Suspense fallback={<ChartFallback />}>
                <GeneCoverageChart data={geneChartData} />
              </Suspense>
            ) : (
              <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 text-center">
                <p className="text-sm font-semibold text-foreground">No active panel gene counts available</p>
                <p className="mt-1 max-w-md text-xs text-muted-foreground">
                  Active ASP documents need populated covered_genes or germline_genes arrays before the coverage chart can be drawn.
                </p>
              </div>
            )}
          </div>
        </SurfacePanel>

        <SurfacePanel className="dashboard-panel dashboard-panel--rose h-full" title="Panel Portfolio" description="Active targeted-panel design inventory.">
          <div className="grid grid-cols-2 gap-2 xl:h-[320px] xl:auto-rows-fr">
            <Metric title="Active panels" value={panelPortfolio.active_panels} sub={`${fmt(panelPortfolio.accredited_panels)} accredited`} />
            <Metric title="Assay groups" value={panelPortfolio.assay_groups} sub="Represented by active panels" />
            <Metric title="Covered assignments" value={panelPortfolio.covered_gene_assignments} sub="Genes across panel definitions" />
            <Metric title="Germline assignments" value={panelPortfolio.germline_gene_assignments} sub="Configured germline scope" />
          </div>
        </SurfacePanel>
      </div>

      <div className="grid items-stretch gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--blue h-full" title="Panel Analysis Capability" description="Enabled analysis and report sections across active targeted-panel configurations.">
          <div className="h-[280px]">
            {panelAnalysisCapabilityData.length ? (
              <Suspense fallback={<ChartFallback />}>
                <PanelAnalysisCapabilityChart data={panelAnalysisCapabilityData} />
              </Suspense>
            ) : (
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-border text-center text-xs text-muted-foreground">
                No targeted-panel analysis capabilities are configured.
              </div>
            )}
          </div>
        </SurfacePanel>

        <SurfacePanel className="dashboard-panel dashboard-panel--amber h-full" title="Resource Capacity" description="Configured resources and reference inventory.">
          <div className="grid grid-cols-2 gap-2 xl:h-[280px] xl:auto-rows-fr">
            {capacityEntries.length ? capacityEntries.map(([key, value], index) => (
              <div key={key} className="dashboard-subcard p-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="mt-1 text-base font-semibold" style={{ color: chartColors[index % chartColors.length] }}>{fmt(value)}</p>
              </div>
            )) : <p className="text-xs text-muted-foreground">No capacity data available.</p>}
          </div>
        </SurfacePanel>
      </div>

      <SurfacePanel className="dashboard-panel dashboard-panel--amber" title="Clinical Configuration" description="Gene-list visibility and assay coverage for interpretation workflows.">
        <div className="grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
            <Metric title="Unique active genes" value={data?.unique_gene_count_all_panels} sub="Across active ASPs" />
            <Metric title="Public ISGLs" value={isglVisibility.public_total} sub={`${fmt(isglVisibility.public_only)} public only`} />
            <Metric title="Private ISGLs" value={isglVisibility.private_total} sub={`${fmt(isglVisibility.private_only)} private only`} />
            <Metric title="Ad-hoc lists" value={isglVisibility.adhoc_total} sub={`${fmt(isglVisibility.overlap_total)} overlapping`} />
          </div>
          <div className="dashboard-subcard p-2.5">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Top Assay ISGL Associations</h3>
              <Link to="/public/catalog" className="link-text text-[11px] font-medium">Open catalog</Link>
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {isglAssociationRows.length ? isglAssociationRows.slice(0, 6).map((row: any) => (
                <div key={row.assay_id || row.display_name} className="dashboard-subcard p-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-foreground">{row.display_name || row.assay_id}</p>
                      <p className="mt-0.5 truncate text-[10px] font-medium uppercase text-muted-foreground">{row.asp_group || "unassigned"}</p>
                    </div>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">{fmt(row.isgl_total)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="rounded-md bg-pass/10 px-1.5 py-0.5 text-[10px] font-medium text-pass">{fmt(row.public_count)} public</span>
                    <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">{fmt(row.private_count)} private</span>
                    <span className="rounded-md bg-warn/10 px-1.5 py-0.5 text-[10px] font-medium text-warn">{fmt(row.adhoc_count)} ad-hoc</span>
                  </div>
                </div>
              )) : <p className="text-xs text-muted-foreground">No assay-to-ISGL associations configured.</p>}
            </div>
          </div>
        </div>
      </SurfacePanel>
    </PageShell>
  )
}
