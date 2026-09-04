import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Suspense, lazy, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw } from "lucide-react"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { TimeDisplay } from "@/components/ui/time-display"
import { shortCount } from "@/lib/detail-formatters"
import { buildPanelAnalysisCapabilityData, buildPanelGeneChartData } from "@/lib/dashboard-data"
import { sampleDetailPath } from "@/lib/sample-routing"
import { notifyActionError, notifySuccess, notifyWarning } from "@/lib/notifications"
import { cn } from "@/lib/utils"
import { KnowledgebaseStatus } from "@/components/knowledgebase/KnowledgebaseStatus"

const chartColors = ["var(--color-tier1)", "var(--color-tier2)", "var(--color-tier3)", "var(--color-tier4)", "var(--color-dna)", "var(--color-rna)", "var(--color-panel)"]
const TierDistributionChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.TierDistributionChart })))
const GeneCoverageChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.GeneCoverageChart })))
const PanelAnalysisCapabilityChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.PanelAnalysisCapabilityChart })))
const SampleCompositionCharts = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.SampleCompositionCharts })))
const TopTieredGenesChart = lazy(() => import("@/components/dashboard/DashboardCharts").then((module) => ({ default: module.TopTieredGenesChart })))

const dashboardMetrics = [
  { key: "samples", path: "/dashboard/metrics/samples" },
  { key: "findings", path: "/dashboard/metrics/findings" },
  { key: "top_tiered_genes", path: "/dashboard/metrics/top-tiered-genes" },
  { key: "panels", path: "/dashboard/metrics/panels" },
  { key: "clinical_configuration", path: "/dashboard/metrics/clinical-configuration" },
  { key: "resources", path: "/dashboard/metrics/resources" },
] as const

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

function ChartFallback() {
  return (
    <div className="flex h-full items-center justify-center rounded-lg bg-muted/40 text-xs font-semibold text-muted-foreground">
      Loading chart...
    </div>
  )
}

function MetricUnavailable({ label }: { label: string }) {
  return (
    <div className="flex min-h-24 items-center justify-center rounded-lg border border-dashed border-destructive/30 bg-destructive/5 px-4 py-6 text-center type-body-sm text-muted-foreground">
      <span>
        <AlertTriangle className="mr-2 inline h-4 w-4 text-destructive" />
        {label} is temporarily unavailable.
      </span>
    </div>
  )
}

export function Dashboard() {
  const queryClient = useQueryClient()
  const [refreshStartedAt, setRefreshStartedAt] = useState<number | null>(null)
  const metricQueries = useQueries({
    queries: dashboardMetrics.map((metric) => ({
      queryKey: ["dashboard-metric", metric.key],
      queryFn: () => api.get(metric.path).then((response) => response.data?.payload || response.data),
      refetchInterval: 60_000,
    })),
  })
  const knowledgebaseQuery = useQuery({
    queryKey: ["knowledgebase-status"],
    queryFn: () => api.get("/public/knowledgebases/status").then((response) => response.data),
    staleTime: 5 * 60 * 1000,
  })
  const data = metricQueries.reduce<Record<string, any>>((combined, query) => {
    const payload = query.data || {}
    return {
      ...combined,
      ...payload,
      quality_stats: {
        ...(combined.quality_stats || {}),
        ...(payload.quality_stats || {}),
      },
    }
  }, {})
  const metricMetadata = metricQueries
    .map((query) => query.data?.metric_meta)
    .filter(Boolean)
  const generatedAtSignature = metricMetadata
    .map((meta) => String(meta?.generated_at || ""))
    .join("|")
  const failedMetrics = metricQueries
    .map((query, index) => (query.error ? dashboardMetrics[index].key : null))
    .filter(Boolean)
  const unavailableMetrics = new Set(
    metricQueries
      .map((query, index) => (query.error && !query.data ? dashboardMetrics[index].key : null))
      .filter(Boolean),
  )
  const isUnavailable = (metric: (typeof dashboardMetrics)[number]["key"]) => unavailableMetrics.has(metric)
  const refreshMutation = useMutation({
    mutationFn: () => api.post("/dashboard/metrics/refresh", {
      metrics: dashboardMetrics.map((metric) => metric.key),
    }),
    onMutate: () => setRefreshStartedAt(Date.now()),
    onError: (mutationError) => {
      setRefreshStartedAt(null)
      notifyActionError("Dashboard refresh could not be queued", mutationError, "Dashboard")
    },
  })
  const refreshPending = refreshStartedAt !== null

  useEffect(() => {
    if (refreshStartedAt === null) return
    const generatedTimes = generatedAtSignature
      .split("|")
      .filter(Boolean)
      .map((value) => Date.parse(value))
    const allUpdated = generatedTimes.length === dashboardMetrics.length
      && generatedTimes.every((generatedAt) => Number.isFinite(generatedAt) && generatedAt >= refreshStartedAt - 1000)
    if (allUpdated) {
      setRefreshStartedAt(null)
      notifySuccess("Dashboard metrics updated", "The latest metrics are now displayed.", "Dashboard")
      return
    }
    const interval = window.setInterval(() => {
      void queryClient.refetchQueries({ queryKey: ["dashboard-metric"] })
    }, 2000)
    const timeout = window.setTimeout(() => {
      window.clearInterval(interval)
      setRefreshStartedAt(null)
      notifyWarning(
        "Dashboard refresh is still running",
        "Current values remain available. Updated metrics will appear automatically when ready.",
        "Dashboard",
      )
    }, 120000)
    return () => {
      window.clearInterval(interval)
      window.clearTimeout(timeout)
    }
  }, [generatedAtSignature, queryClient, refreshStartedAt])

  const refreshButton = (
    <Button
      type="button"
      size="sm"
      variant="outline"
      disabled={refreshMutation.isPending || refreshPending}
      onClick={() => refreshMutation.mutate()}
      title="Queue a background refresh of dashboard metrics"
    >
      <RefreshCw className={cn("h-4 w-4", refreshPending && "animate-spin")} />
      {refreshPending ? "Refreshing" : "Refresh metrics"}
    </Button>
  )

  if (metricQueries.every((query) => query.isLoading && !query.data)) {
    return <AppLoader label="Loading dashboard" />
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
  const pipelineData = Array.isArray(scopeStats.pipelines) ? scopeStats.pipelines : []
  const topTieredGenes = Array.isArray(data?.top_tiered_genes)
    ? data.top_tiered_genes.slice(0, 15)
    : []

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
  const compositionGroups = [
    { name: "Ingest status", rows: statusData },
    { name: "Omics", rows: omicsData },
    { name: "Sequencing scope", rows: scopeData },
    { name: "My profile scope", rows: Object.entries(scopeStats.profiles || {}).map(([name, value]) => ({ name, value: Number(value) })) },
    { name: "Pairing", rows: pairingData },
  ]
  const variantClassData = Object.entries(vStats.by_variant_class || {}).map(([name, value]) => ({ name, value: Number(value) })).sort((a, b) => b.value - a.value)
  const capacityEntries = Object.entries(capacity)

  return (
    <PageShell
      eyebrow="Operations"
      title="Dashboard"
      description="Throughput, quality, tiering, assay scope, and resource health."
      className="gap-3"
      actions={
        <>
          {refreshButton}
          <Link to="/samples" className={buttonVariants({ size: "sm" })}>Open samples</Link>
          <Link to="/variants/search" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "paper-raised-control")}>Variant search</Link>
          <Link to="/public/catalog" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "paper-raised-control")}>Catalog</Link>
        </>
      }
    >

      {failedMetrics.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <span>
            <AlertTriangle className="mr-2 inline h-4 w-4" />
            Some dashboard sections could not be updated: {failedMetrics.join(", ").replaceAll("_", " ")}.
          </span>
          {refreshButton}
        </div>
      )}

      {(metricMetadata.some((meta) => meta?.stale) || refreshPending) && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-foreground">
          {refreshPending ? (
            <span>Dashboard metrics are refreshing in the background. Current values remain available.</span>
          ) : (
            <span>One or more dashboard sections are showing cached values while updated metrics are prepared.</span>
          )}
        </div>
      )}

      <SurfacePanel className="dashboard-panel" title="Operational Snapshot" description="Current clinical workload, analysis progress, and finding volume.">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[1.45fr_1fr_1fr]">
          <div className="dashboard-snapshot-card p-3">
            {isUnavailable("samples") ? <MetricUnavailable label="Sample progress" /> : <>
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
            </>}
          </div>
          <div className="dashboard-snapshot-card p-3">
            {isUnavailable("samples") ? <MetricUnavailable label="Visible sample count" /> : <>
            <p className="type-label text-muted-foreground">My visible samples</p>
            <p className="mt-1 text-xl font-semibold leading-tight text-foreground">{fmt(userScope.total_samples ?? data?.total_samples)}</p>
            <p className="type-meta mt-2 text-muted-foreground">Available through your roles, assays, and environments.</p>
            </>}
          </div>
          <div className="dashboard-snapshot-card p-3">
            {isUnavailable("findings") ? <MetricUnavailable label="Finding inventory" /> : <>
            <p className="type-label text-muted-foreground">Finding inventory</p>
            <p className="mt-1 text-xl font-semibold leading-tight text-foreground">{fmt(findingTotal)}</p>
            <p className="type-meta mt-2 text-muted-foreground">Small variant, CNV, fusion, and translocation records.</p>
            </>}
          </div>
        </div>
      </SurfacePanel>

      <div className="grid items-stretch gap-3 xl:grid-cols-[1.05fr_0.95fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--teal h-full" title="Review Workload" description="Assay progress and profile distribution.">
          {isUnavailable("samples") ? <MetricUnavailable label="Review workload" /> : (
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
          )}
        </SurfacePanel>

        <SurfacePanel className="dashboard-panel dashboard-panel--rose h-full" title="My Recent Samples" description="Latest samples visible to your account.">
          {isUnavailable("samples") ? <MetricUnavailable label="Recent samples" /> : <>
          <div className="space-y-2">
            {recentSamples.length ? recentSamples.map((sample: any) => (
              <Link key={sample.id || sample.name} to={sampleDetailPath(sample, sample.id)} className="dashboard-subcard group flex items-center justify-between gap-3 p-2.5 hover:border-primary/40 hover:bg-primary/5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-primary">{sample.name || sample.id}</p>
                    <span className="type-badge rounded-md bg-dna/10 px-1.5 py-0.5 uppercase text-dna">{sample.omics_layer || "dna"}</span>
                    <span className="type-badge rounded-md bg-muted px-1.5 py-0.5 uppercase text-muted-foreground">{sample.ingest_status || "unknown"}</span>
                  </div>
                  <p className="type-meta mt-0.5 flex min-w-0 items-center gap-1 truncate text-muted-foreground">
                    <span className="truncate">
                      {sample.asp_id || "-"} {sample.subpanel_id ? `• ${sample.subpanel_id}` : ""}
                    </span>
                    <span aria-hidden="true">•</span>
                    <TimeDisplay value={sample.time_added} className="shrink-0" />
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
          </>}
        </SurfacePanel>
      </div>

      <div className="grid items-stretch gap-3 2xl:grid-cols-[0.9fr_1.1fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--amber h-full" title="Sample Composition" description="Profiles, status, modality, and sequencing scope.">
          {isUnavailable("samples") ? <MetricUnavailable label="Sample composition" /> : (
          <Suspense fallback={<ChartFallback />}>
            <SampleCompositionCharts groups={compositionGroups} pipelines={pipelineData} colors={chartColors} />
          </Suspense>
          )}
        </SurfacePanel>

        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          <SurfacePanel className="dashboard-panel dashboard-panel--blue" title="Variant Review" description="Finding counts and classification quality indicators.">
            {isUnavailable("findings") ? <MetricUnavailable label="Finding review metrics" /> : (
            <div className="grid items-stretch gap-3 lg:grid-cols-[minmax(0,1.55fr)_minmax(16rem,0.8fr)_minmax(14rem,0.7fr)]">
              <div className="grid grid-cols-2 gap-2 break-words md:grid-cols-4">
                <Metric title="Small variants" value={vStats.snv || vStats.small_variants} sub={`${fmt(vStats.snps)} SNV/SNP class`} />
                <Metric title="CNV" value={vStats.cnv || vStats.cnvs} />
                <Metric title="Fusions" value={vStats.fusion || vStats.fusions} />
                <Metric title="Translocations" value={vStats.translocation || vStats.translocations} />
                <Metric title="Blacklisted" value={vStats.blacklisted} />
                <Metric title="False positives" value={vStats.fps ?? vStats.false_positives} sub={`${quality.fp_rate_percent ?? quality.false_positive_rate_percent ?? 0}%`} />
                <Metric title="Tier 1/2" value={vStats.tier1_or_2 ?? vStats.pathogenic} sub="Report-priority findings" />
                <Metric title="VUS (Tier 3)" value={vStats.vus} />
                <Metric title="Reported findings" value={vStats.reported_findings} sub="Saved report snapshots" />
                <Metric title="Benign (Tier 4)" value={vStats.tier4} sub="Not included in reports" />
              </div>
              <div className="min-h-64 min-w-0">
                {tierChartData.length ? (
                  <div className="h-full min-h-64 min-w-0">
                    <Suspense fallback={<ChartFallback />}>
                      <TierDistributionChart data={tierChartData} colors={chartColors} />
                    </Suspense>
                  </div>
                ) : <p className="text-xs text-muted-foreground">No tier data available.</p>}
              </div>
              <div className="dashboard-subcard min-h-48 p-2">
                <h3 className="mb-2 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Small Variant Classes</h3>
                <div className="space-y-2">
                  {variantClassData.length ? variantClassData.slice(0, 6).map((item, index) => (
                    <div key={item.name} className="space-y-1">
                      <div className="flex justify-between gap-3 type-meta font-medium uppercase">
                        <span className="truncate">{item.name || "unknown"}</span>
                        <span>{fmt(item.value)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(100, (item.value / Math.max(...variantClassData.map((row) => row.value), 1)) * 100)}%`, background: chartColors[index % chartColors.length] }} />
                      </div>
                    </div>
                  )) : <p className="text-xs text-muted-foreground">No class data available.</p>}
                </div>
              </div>
            </div>
            )}
          </SurfacePanel>

          <SurfacePanel className="dashboard-panel dashboard-panel--rose flex min-h-0 flex-1 flex-col" title="Panel Portfolio" description="Active targeted-panel design inventory.">
            {isUnavailable("panels") ? <MetricUnavailable label="Panel portfolio" /> : (
            <div className="grid min-h-0 flex-1 auto-rows-fr grid-cols-2 gap-2">
              <Metric title="Active panels" value={panelPortfolio.active_panels} sub={`${fmt(panelPortfolio.accredited_panels)} accredited`} />
              <Metric title="Assay groups" value={panelPortfolio.assay_groups} sub="Represented by active panels" />
              <Metric title="Covered assignments" value={panelPortfolio.covered_gene_assignments} sub="Genes across panel definitions" />
              <Metric title="Germline assignments" value={panelPortfolio.germline_gene_assignments} sub="Configured germline scope" />
            </div>
            )}
          </SurfacePanel>
        </div>
      </div>

      <SurfacePanel
        className="dashboard-panel dashboard-panel--teal"
        title="Top Tiered Genes"
        description="Current classified annotation identities ranked across all supported nomenclatures."
      >
        {isUnavailable("top_tiered_genes") ? <MetricUnavailable label="Top tiered genes" /> : topTieredGenes.length ? (
          <Suspense fallback={<ChartFallback />}>
            <TopTieredGenesChart data={topTieredGenes} />
          </Suspense>
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-center type-body-sm text-muted-foreground">
            No tiered gene data available.
          </div>
        )}
      </SurfacePanel>

      <SurfacePanel
        className="dashboard-panel dashboard-panel--blue"
        title="Knowledgebase Inventory"
        description="Installed reference products, releases, and indexed evidence available to interpretation views."
      >
        {knowledgebaseQuery.isLoading ? (
          <AppLoader label="Loading knowledgebase inventory" />
        ) : knowledgebaseQuery.error ? (
          <MetricUnavailable label="Knowledgebase inventory" />
        ) : (
          <KnowledgebaseStatus payload={knowledgebaseQuery.data} compact />
        )}
      </SurfacePanel>

      <div className="grid items-stretch gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <SurfacePanel className="dashboard-panel dashboard-panel--teal h-full" title="Panel Gene Coverage" description="Covered and germline gene scope across active targeted panels.">
          {isUnavailable("panels") ? <MetricUnavailable label="Panel gene coverage" /> : (
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
          )}
        </SurfacePanel>

        <SurfacePanel className="dashboard-panel dashboard-panel--amber h-full" title="Resource Capacity" description="Configured resources and reference inventory.">
          {isUnavailable("resources") ? <MetricUnavailable label="Resource capacity" /> : (
          <div className="grid grid-cols-2 gap-2 xl:h-[320px] xl:auto-rows-fr">
            {capacityEntries.length ? capacityEntries.map(([key, value], index) => (
              <div key={key} className="dashboard-subcard p-2.5">
                <p className="type-label font-semibold uppercase tracking-wide text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="mt-1 text-base font-semibold" style={{ color: chartColors[index % chartColors.length] }}>{fmt(value)}</p>
              </div>
            )) : <p className="text-xs text-muted-foreground">No capacity data available.</p>}
          </div>
          )}
        </SurfacePanel>
      </div>

      <SurfacePanel className="dashboard-panel dashboard-panel--blue">
        {isUnavailable("panels") ? <MetricUnavailable label="Panel analysis capabilities" /> : (
        <div className="h-[300px]">
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
        )}
      </SurfacePanel>

      <SurfacePanel className="dashboard-panel dashboard-panel--amber" title="Clinical Configuration" description="Gene-list visibility and assay coverage for interpretation workflows.">
        {isUnavailable("clinical_configuration") ? <MetricUnavailable label="Clinical configuration" /> : (
        <div className="grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
            <Metric title="Unique active genes" value={data?.unique_gene_count_all_panels} sub="Across active ASPs" />
            <Metric title="Public ISGLs" value={isglVisibility.public_total} sub={`${fmt(isglVisibility.public_only)} public only`} />
            <Metric title="Private ISGLs" value={isglVisibility.private_total} sub={`${fmt(isglVisibility.private_only)} private only`} />
            <Metric title="Ad-hoc lists" value={isglVisibility.adhoc_total} sub={`${fmt(isglVisibility.overlap_total)} overlapping`} />
          </div>
          <div className="dashboard-subcard p-2.5">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="type-meta font-semibold uppercase tracking-wide text-muted-foreground">Top Assay ISGL Associations</h3>
              <Link to="/public/catalog" className="link-text type-meta font-medium">Open catalog</Link>
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {isglAssociationRows.length ? isglAssociationRows.slice(0, 6).map((row: any) => (
                <div key={row.assay_id || row.display_name} className="dashboard-subcard p-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-foreground">{row.display_name || row.assay_id}</p>
                      <p className="mt-0.5 truncate type-label font-medium uppercase text-muted-foreground">{row.asp_group || "unassigned"}</p>
                    </div>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 type-meta font-semibold text-primary">{fmt(row.isgl_total)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <span className="rounded-md bg-pass/10 px-1.5 py-0.5 type-label font-medium text-pass">{fmt(row.public_count)} public</span>
                    <span className="rounded-md bg-primary/10 px-1.5 py-0.5 type-label font-medium text-primary">{fmt(row.private_count)} private</span>
                    <span className="rounded-md bg-warn/10 px-1.5 py-0.5 type-label font-medium text-warn">{fmt(row.adhoc_count)} ad-hoc</span>
                  </div>
                </div>
              )) : <p className="text-xs text-muted-foreground">No assay-to-ISGL associations configured.</p>}
            </div>
          </div>
        </div>
        )}
      </SurfacePanel>
    </PageShell>
  )
}
