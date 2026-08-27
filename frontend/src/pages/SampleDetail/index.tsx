import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { SegmentedControl } from "@/components/ui/segmented-control"

import { OverviewTab, PanelSummary } from "./OverviewTab"
import { SampleDetailHero } from "./SampleDetailHero"
import { VariantsTab } from "./VariantsTab"
import { CNVTab } from "./CNVTab"
import { FusionsTab } from "./FusionsTab"
import { TranslocationsTab } from "./TranslocationsTab"
import { ReportsTab } from "./ReportsTab"
import { CoverageTab } from "./CoverageTab"
import { RnaAnalysisTab } from "./RnaAnalysisTabs"
import { FiltersSidebar } from "./FiltersSidebar"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageFrame } from "@/components/layout/PageFrame"
import { LayoutDiscoveryBanner } from "@/components/layout/LayoutDiscoveryBanner"
import { hasSampleFile } from "@/lib/sample-shape"
import { sampleUrlKey } from "@/lib/sample-routing"
import { moduleIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { useCurrentUserAccess } from "@/lib/access-control"
import {
  analysisLayoutForUser,
  analysisModernViewTriedForUser,
  useUpdateUiSettings,
  type AnalysisLayout,
} from "@/lib/user-settings"
import { FindingsTab, type FindingSectionId } from "./FindingsTab"

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "snvs", label: "Somatic SNVs", analysis: "SNV", intent: "somatic" },
  { id: "germline-snvs", label: "Germline SNVs", analysis: "SNV", intent: "germline" },
  { id: "cnvs", label: "CNVs", analysis: "CNV" },
  { id: "fusions", label: "Fusions", analysis: "FUSION" },
  { id: "rna-analysis", label: "Expression & Classification", analysis: "RNA_ANALYSIS" },
  { id: "translocations", label: "Translocations", analysis: "TRANSLOCATION" },
  { id: "coverage", label: "Coverage", analysis: "COVERAGE" },
  { id: "reports", label: "Reports" }
]

const FINDING_TAB_IDS = new Set([
  "snvs",
  "germline-snvs",
  "cnvs",
  "fusions",
  "rna-analysis",
  "translocations",
])

const FILTERABLE_FINDING_TAB_IDS = new Set([
  "snvs",
  "germline-snvs",
  "cnvs",
  "fusions",
  "translocations",
])

function visibleTabs(sample: any, context: any, modules?: any) {
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
    if (tab.id === "reports") return moduleIsEnabled(modules, "reports")
    if (["snvs", "germline-snvs", "cnvs", "translocations", "coverage"].includes(tab.id) && !moduleIsEnabled(modules, "dna_analysis")) return false
    if (["fusions", "rna-analysis"].includes(tab.id) && !moduleIsEnabled(modules, "rna_analysis")) return false
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
    if (tab.id === "rna-analysis") {
      const hasExpression = (hasSampleFile(sample, "expression_path") || hasCount("rna_expression")) && hasAnalysis("EXPRESSION")
      const hasClassification = (hasSampleFile(sample, "classification_path") || hasCount("rna_classification")) && hasAnalysis("CLASSIFICATION")
      return omicsLayer === "rna" && (hasExpression || hasClassification)
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
  const modulesQuery = useApplicationModules()
  const currentUserQuery = useCurrentUserAccess()
  const updateUiSettings = useUpdateUiSettings()
  const [filterToggleRequest, setFilterToggleRequest] = useState<{
    sequence: number
    section: FindingSectionId
  } | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['sample', id],
    queryFn: () => api.get(`/samples/${id}/edit-context`).then(res => res.data),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  })
  const sample = data?.sample || {}
  const sampleRouteKey = sampleUrlKey(sample, id)
  const sampleReportType: "dna" | "rna" =
    String(sample?.omics_layer || "").toLowerCase() === "rna" ? "rna" : "dna"
  const tabs = useMemo(() => visibleTabs(data?.sample || {}, data, modulesQuery.data), [data, modulesQuery.data])
  const analysisLayout = analysisLayoutForUser(currentUserQuery.data)
  const modernViewTried = analysisModernViewTriedForUser(currentUserQuery.data)
  const findingSections = useMemo(
    () => tabs.filter((tab) => FINDING_TAB_IDS.has(tab.id)),
    [tabs],
  )
  const navigationTabs = useMemo(() => {
    if (analysisLayout === "modern") return tabs
    const compactTabs = tabs.filter((tab) => ["overview", "coverage", "reports"].includes(tab.id))
    if (findingSections.length > 0) {
      compactTabs.splice(1, 0, { id: "findings", label: "Findings" })
    }
    return compactTabs
  }, [analysisLayout, findingSections.length, tabs])
  const canonicalRequestedTab = requestedTab === "snvs" && requestedIntent === "germline"
    ? "germline-snvs"
    : ["expression", "classification"].includes(requestedTab) ? "rna-analysis" : requestedTab
  const requestedFindingTab = FINDING_TAB_IDS.has(canonicalRequestedTab) ? canonicalRequestedTab : null
  const activeTab = analysisLayout === "classic" && requestedFindingTab
    ? "findings"
    : navigationTabs.some((tab) => tab.id === canonicalRequestedTab) ? canonicalRequestedTab : "overview"
  const requestedFilterSection = searchParams.get("finding_filter") || requestedFindingTab
  const firstFilterableFinding = findingSections.find((tab) => FILTERABLE_FINDING_TAB_IDS.has(tab.id))?.id || null
  const activeFindingFilter = analysisLayout === "classic" && activeTab === "findings"
    ? findingSections.some((tab) => tab.id === requestedFilterSection && FILTERABLE_FINDING_TAB_IDS.has(tab.id))
      ? requestedFilterSection
      : firstFilterableFinding
    : null
  const filterTab = activeTab === "findings" ? activeFindingFilter : activeTab
  const activeIntent = filterTab === "germline-snvs" ? "germline" : "somatic"
  const showComments = activeTab === "findings" || ["snvs", "germline-snvs", "cnvs", "fusions", "translocations"].includes(activeTab)
  const showFilters = Boolean(activeFindingFilter) || ["snvs", "germline-snvs", "cnvs", "fusions", "translocations", "coverage"].includes(activeTab)
  const suggestionPath = String(sample?.omics_layer || "").toLowerCase() === "rna"
    ? `/samples/${sampleRouteKey}/fusions/comment-suggestion`
    : `/samples/${sampleRouteKey}/small-variants/comment-suggestion`
  const commentSuggestion = useQuery({
    queryKey: ["sample-comment-suggestion", sampleRouteKey, sample?.omics_layer, activeIntent],
    queryFn: () => api.get(`${suggestionPath}?intent=${activeIntent}`).then((res) => res.data),
    enabled: false,
    staleTime: 60_000,
  })
  const requestCommentSuggestion = async () => {
    if (!data || !showComments || !sampleRouteKey) return ""
    const result = await commentSuggestion.refetch()
    return String(result.data?.suggested_text || "")
  }
  useEffect(() => {
    if (sample?.name && id && id !== sample.name) {
      const query = searchParams.toString()
      navigate(`/samples/${encodeURIComponent(sample.name)}${query ? `?${query}` : ""}`, { replace: true })
    }
  }, [id, navigate, sample?.name, searchParams])
  useEffect(() => {
    if (!data || navigationTabs.some((tab) => tab.id === canonicalRequestedTab) || (analysisLayout === "classic" && requestedFindingTab)) return
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.delete("tab")
      return params
    }, { replace: true })
  }, [analysisLayout, canonicalRequestedTab, data, navigationTabs, requestedFindingTab, setSearchParams])

  const selectTab = (tabId: string) => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (tabId === "overview") params.delete("tab")
      else params.set("tab", tabId)
      if (tabId === "germline-snvs") params.set("intent", "germline")
      else params.delete("intent")
      if (tabId !== "findings") params.delete("finding_filter")
      return params
    }, { replace: true })
  }

  const selectFindingFilter = (tabId: FindingSectionId) => {
    setFilterToggleRequest((request) => ({
      sequence: (request?.sequence ?? 0) + 1,
      section: tabId,
    }))
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.set("tab", "findings")
      params.set("finding_filter", tabId)
      params.delete("intent")
      return params
    }, { replace: true })
  }

  const selectAnalysisLayout = (layout: AnalysisLayout) => {
    if (layout === analysisLayout || updateUiSettings.isPending) return
    updateUiSettings.mutate({
      analysis_layout: layout,
      ...(layout === "modern" ? { analysis_modern_view_tried: true } : {}),
    })
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (layout === "classic" && FINDING_TAB_IDS.has(activeTab)) {
        params.set("tab", "findings")
        params.set("finding_filter", activeTab)
        params.delete("intent")
      } else if (layout === "modern" && activeTab === "findings") {
        const target = activeFindingFilter || findingSections[0]?.id || "overview"
        if (target === "overview") params.delete("tab")
        else params.set("tab", target)
        if (target === "germline-snvs") params.set("intent", "germline")
        else params.delete("intent")
        params.delete("finding_filter")
      }
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
    <PageFrame className="flex-1">
      <SampleDetailHero sample={sample} context={data} />

      <div className="mt-3 flex gap-3">
          {/* Main Content Area */}
          <div className="flex-1 min-w-0">
            <div className="rounded-xl overflow-hidden py-1 lg:py-2">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 glass-panel p-1">
                <div className="overflow-x-auto whitespace-nowrap scrollbar-none">
                  <SegmentedControl
                    ariaLabel="Sample analysis views"
                    className="min-w-max"
                    value={activeTab}
                    onValueChange={selectTab}
                    items={navigationTabs.map((tab) => ({ value: tab.id, label: tab.label }))}
                  />
                </div>
                <SegmentedControl
                  ariaLabel="Analysis layout"
                  className="min-w-[190px]"
                  value={analysisLayout}
                  onValueChange={selectAnalysisLayout}
                  items={[
                    { value: "classic", label: "Classic" },
                    { value: "modern", label: "Modern" },
                  ]}
                />
              </div>

              {analysisLayout === "classic" && !modernViewTried && (
                <div className="mb-3">
                  <LayoutDiscoveryBanner onTryModern={() => selectAnalysisLayout("modern")} />
                </div>
              )}

              <div className="space-y-3">
                {activeTab !== "overview" && activeTab !== "coverage" && (
                  <PanelSummary sample={sample} context={data} />
                )}

                {activeTab === "overview" && (
                  <OverviewTab sampleId={sampleRouteKey} sample={sample} context={data} />
                )}
                {activeTab === "snvs" && <VariantsTab sampleId={sampleRouteKey} intent="somatic" />}
                {activeTab === "germline-snvs" && (
                  <VariantsTab sampleId={sampleRouteKey} intent="germline" />
                )}
                {activeTab === "findings" && (
                  <FindingsTab
                    sampleId={sampleRouteKey}
                    sections={findingSections as Array<{ id: FindingSectionId; label: string }>}
                    activeFilterSection={activeFindingFilter as FindingSectionId | null}
                    onSelectFilterSection={selectFindingFilter}
                  />
                )}
                {activeTab === "cnvs" && <CNVTab sampleId={sampleRouteKey} />}
                {activeTab === "fusions" && <FusionsTab sampleId={sampleRouteKey} />}
                {activeTab === "rna-analysis" && <RnaAnalysisTab sampleId={sampleRouteKey} />}
                {activeTab === "translocations" && <TranslocationsTab sampleId={sampleRouteKey} />}
                {activeTab === "coverage" && <CoverageTab sampleId={sampleRouteKey} sample={sample} />}
                {activeTab === "reports" && (
                  <ReportsTab sampleId={sampleRouteKey} reportType={sampleReportType} />
                )}
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
                  onRequestSuggestion={requestCommentSuggestion}
                />
              </div>
            )}
          </div>

          {showFilters && (
            <FiltersSidebar
              sampleId={sampleRouteKey}
              sample={sample}
              context={data}
              activeTab={filterTab || "overview"}
              intent={activeIntent}
              availableSections={activeTab === "findings"
                ? findingSections
                  .filter((tab) => FILTERABLE_FINDING_TAB_IDS.has(tab.id))
                  .map((tab) => ({ id: tab.id, label: tab.label }))
                : []}
              onSelectSection={activeTab === "findings"
                ? (section) => selectFindingFilter(section as FindingSectionId)
                : undefined}
              toggleRequest={filterToggleRequest}
            />
          )}
      </div>
    </PageFrame>
  )
}
