import { useEffect, useMemo } from "react"
import { useNavigate, useParams, Link, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { AlertTriangle, ArrowLeft } from "lucide-react"

import { BiomarkerRow, OverviewTab, PanelSummary } from "./OverviewTab"
import { VariantsTab } from "./VariantsTab"
import { CNVTab } from "./CNVTab"
import { FusionsTab } from "./FusionsTab"
import { TranslocationsTab } from "./TranslocationsTab"
import { ReportsTab } from "./ReportsTab"
import { CoverageTab } from "./CoverageTab"
import { FiltersSidebar } from "./FiltersSidebar"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { AppLoader } from "@/components/layout/AppLoader"
import { hasSampleFile } from "@/lib/sample-shape"
import { sampleUrlKey } from "@/lib/sample-routing"

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "snvs", label: "Somatic SNVs", analysis: "SNV", intent: "somatic" },
  { id: "germline-snvs", label: "Germline SNVs", analysis: "SNV", intent: "germline" },
  { id: "cnvs", label: "CNVs", analysis: "CNV" },
  { id: "fusions", label: "Fusions", analysis: "FUSION" },
  { id: "translocations", label: "Translocations", analysis: "TRANSLOCATION" },
  { id: "coverage", label: "Coverage", analysis: "COVERAGE" },
  { id: "reports", label: "Reports" }
]

function visibleTabs(sample: any, context: any) {
  const configured = new Set((context?.analysis_sections || []).map((item: string) => String(item).toUpperCase()))
  const hasCount = (key: string) => {
    const value = sample?.data_counts?.[key]
    return value === true || Number(value || 0) > 0
  }
  const hasAnalysis = (...keys: string[]) => keys.some((key) => configured.has(key))
  const omicsLayer = String(sample?.omics_layer || "").toLowerCase()
  const analysisIntents = new Set(
    (Array.isArray(sample?.analysis_intents) ? sample.analysis_intents : ["somatic"])
      .map((intent: unknown) => String(intent).toLowerCase()),
  )
  return TABS.filter((tab) => {
    if (tab.id === "coverage") {
      const isDna = String(sample?.omics_layer || "").toLowerCase() === "dna"
      const hasResource = hasSampleFile(sample, "cov") || hasCount("cov")
      return isDna && hasResource && hasAnalysis("COVERAGE")
    }
    if (!("analysis" in tab)) return true
    if (tab.id === "snvs" || tab.id === "germline-snvs") {
      const hasResource = hasSampleFile(sample, "vcf_files") || hasCount("snvs")
      return (
        hasResource &&
        analysisIntents.has(tab.intent || "somatic") &&
        hasAnalysis("SNV", "SMALL_VARIANT")
      )
    }
    if (tab.id === "cnvs") {
      const hasResource = hasSampleFile(sample, "cnv") || hasCount("cnvs")
      return hasResource && hasAnalysis("CNV")
    }
    if (tab.id === "translocations") {
      const hasResource = hasSampleFile(sample, "transloc") || hasCount("transloc")
      return hasResource && hasAnalysis("TRANSLOCATION", "TRANSLOC")
    }
    if (tab.id === "fusions") {
      const hasResource = hasSampleFile(sample, "fusion_files") || hasCount("fusions")
      return omicsLayer === "rna" && hasResource && hasAnalysis("FUSION")
    }
    return configured.has(String(tab.analysis).toUpperCase())
  })
}

export function SampleDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get("tab") || "overview"
  const requestedIntent = searchParams.get("intent") === "germline" ? "germline" : "somatic"

  const { data, isLoading, error } = useQuery({
    queryKey: ['sample', id],
    queryFn: () => api.get(`/samples/${id}/edit-context`).then(res => res.data)
  })
  const sample = data?.sample || {}
  const sampleRouteKey = sampleUrlKey(sample, id)
  const tabs = useMemo(() => visibleTabs(data?.sample || {}, data), [data])
  const canonicalRequestedTab = requestedTab === "snvs" && requestedIntent === "germline"
    ? "germline-snvs"
    : requestedTab
  const activeTab = tabs.some((tab) => tab.id === canonicalRequestedTab) ? canonicalRequestedTab : "overview"
  const activeIntent = activeTab === "germline-snvs" ? "germline" : "somatic"
  const showComments = ["snvs", "germline-snvs", "cnvs", "fusions", "translocations"].includes(activeTab)
  const showFilters = ["snvs", "germline-snvs", "cnvs", "fusions", "translocations"].includes(activeTab)
  const suggestionPath = String(sample?.omics_layer || "").toLowerCase() === "rna"
    ? `/samples/${sampleRouteKey}/fusions/comment-suggestion`
    : `/samples/${sampleRouteKey}/small-variants/comment-suggestion`
  const { data: commentSuggestion } = useQuery({
    queryKey: ["sample-comment-suggestion", sampleRouteKey, sample?.omics_layer, activeIntent],
    queryFn: () => api.get(`${suggestionPath}?intent=${activeIntent}`).then((res) => res.data),
    enabled: Boolean(data) && showComments && Boolean(sampleRouteKey),
    staleTime: 60_000,
  })
  useEffect(() => {
    if (sample?.name && id && id !== sample.name) {
      const query = searchParams.toString()
      navigate(`/samples/${encodeURIComponent(sample.name)}${query ? `?${query}` : ""}`, { replace: true })
    }
  }, [id, navigate, sample?.name, searchParams])
  useEffect(() => {
    if (!data || tabs.some((tab) => tab.id === canonicalRequestedTab)) return
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.delete("tab")
      return params
    }, { replace: true })
  }, [canonicalRequestedTab, data, setSearchParams, tabs])

  const selectTab = (tabId: string) => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (tabId === "overview") params.delete("tab")
      else params.set("tab", tabId)
      if (tabId === "germline-snvs") params.set("intent", "germline")
      else params.delete("intent")
      return params
    }, { replace: true })
  }

  if (isLoading) {
    return <AppLoader label="Loading sample" />
  }

  if (error) {
    return (
      <div className="p-8 text-destructive">
        <h2 className="text-2xl font-bold mb-4">Error loading sample</h2>
        <p>{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <div className="w-full max-w-[2600px] flex-1 space-y-3 pt-1">
        <div className="detail-hero">
          <div className="relative z-10 flex items-center gap-4">
          <Link to="/samples" className="soft-icon-button p-2">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="min-w-0">
            <h2 className="brand-gradient-text text-3xl font-bold tracking-tight">
              {sample.name || sample.case_id || id}
            </h2>
            <p className="text-muted-foreground font-medium uppercase tracking-widest text-xs mt-1">
              {sample.asp_id} • {sample.environment} • {sample.ingest_status}
            </p>
            <BiomarkerRow context={data} />
          </div>
          </div>
        </div>

        {sample?.aspc_resolution?.used_base_configuration && (
          <div className="flex items-start gap-2 rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              {sample.aspc_resolution.warning || "Base ASPC configuration is in use."}
              {" "}Requested subpanel: <strong>{sample.aspc_resolution.requested_subpanel_id}</strong>.
            </span>
          </div>
        )}

        <div className="mt-3 flex gap-3">
          {/* Main Content Area */}
          <div className="flex-1 min-w-0">
            <div className="glass-panel rounded-xl overflow-hidden p-2 lg:p-3">
              <div className="mb-3 flex items-center overflow-x-auto whitespace-nowrap scrollbar-none rounded-lg border border-border bg-background/70 px-1.5 py-1.5 shadow-sm">
                <div className="flex gap-2">
                  {tabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => selectTab(tab.id)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-colors duration-100 ${
                        activeTab === tab.id
                        ? "bg-primary text-primary-foreground shadow-md scale-105"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                {activeTab !== "overview" && <PanelSummary sample={sample} context={data} />}

                {activeTab === "overview" && (
                  <OverviewTab sampleId={sampleRouteKey} sample={sample} context={data} />
                )}
                {activeTab === "snvs" && <VariantsTab sampleId={sampleRouteKey} intent="somatic" />}
                {activeTab === "germline-snvs" && (
                  <VariantsTab sampleId={sampleRouteKey} intent="germline" />
                )}
                {activeTab === "cnvs" && <CNVTab sampleId={sampleRouteKey} />}
                {activeTab === "fusions" && <FusionsTab sampleId={sampleRouteKey} />}
                {activeTab === "translocations" && <TranslocationsTab sampleId={sampleRouteKey} />}
                {activeTab === "coverage" && <CoverageTab sampleId={sampleRouteKey} />}
                {activeTab === "reports" && <ReportsTab sampleId={sampleRouteKey} />}
              </div>
            </div>
            {showComments && (
              <div className="mt-3">
                <CommentsPanel
                  sampleId={sampleRouteKey}
                  title="Sample Comments"
                  comments={data?.comments || sample?.comments || []}
                  queryKeys={[["sample", id]]}
                  allowGlobal={false}
                  suggestedText={commentSuggestion?.suggested_text || ""}
                />
              </div>
            )}
          </div>

          {showFilters && (
            <FiltersSidebar sampleId={sampleRouteKey} sample={sample} context={data} activeTab={activeTab} intent={activeIntent} />
          )}
        </div>
      </div>
    </div>
  )
}
