import { useEffect, useMemo, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Activity, ArrowLeft } from "lucide-react"

import { BiomarkerRow, OverviewTab, PanelSummary } from "./OverviewTab"
import { VariantsTab } from "./VariantsTab"
import { CNVTab } from "./CNVTab"
import { FusionsTab } from "./FusionsTab"
import { TranslocationsTab } from "./TranslocationsTab"
import { ReportsTab } from "./ReportsTab"
import { CoverageTab } from "./CoverageTab"
import { FiltersSidebar } from "./FiltersSidebar"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { hasSampleFile } from "@/lib/sample-shape"

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "snvs", label: "Small Variants", analysis: "SNV" },
  { id: "cnvs", label: "CNVs", analysis: "CNV" },
  { id: "fusions", label: "Fusions", analysis: "FUSION" },
  { id: "translocations", label: "Translocations", analysis: "TRANSLOCATION" },
  { id: "coverage", label: "Coverage", analysis: "COVERAGE" },
  { id: "reports", label: "Reports" }
]

function visibleTabs(sample: any, context: any) {
  const configured = new Set((context?.analysis_sections || []).map((item: string) => String(item).toUpperCase()))
  const hasConfiguredSections = configured.size > 0
  return TABS.filter((tab) => {
    if (!("analysis" in tab)) return true
    if (tab.id === "coverage") return hasSampleFile(sample, "cov") && (!hasConfiguredSections || configured.has("COVERAGE") || configured.has("COV"))
    if (!hasConfiguredSections) return true
    return configured.has(String(tab.analysis).toUpperCase())
  })
}

export function SampleDetail() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState("overview")

  const { data, isLoading, error } = useQuery({
    queryKey: ['sample', id],
    queryFn: () => api.get(`/samples/${id}/edit-context`).then(res => res.data)
  })
  const sample = data?.sample || {}
  const tabs = useMemo(() => visibleTabs(data?.sample || {}, data), [data])
  useEffect(() => {
    if (!tabs.some((tab) => tab.id === activeTab)) {
      setActiveTab("overview")
    }
  }, [activeTab, tabs])

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Activity className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 text-destructive">
        <h2 className="text-2xl font-bold mb-4">Error loading sample</h2>
        <p>{error instanceof Error ? error.message : "Unknown error"}</p>
      </div>
    )
  }

  const showComments = ["snvs", "cnvs", "fusions", "translocations"].includes(activeTab)
  const showFilters = ["snvs", "cnvs", "fusions", "translocations"].includes(activeTab)

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <div className="mx-auto w-full max-w-[2600px] flex-1 space-y-3 pt-1">
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
              {sample.assay} • {sample.profile} • {sample.ingest_status}
            </p>
            <BiomarkerRow context={data} />
          </div>
          </div>
        </div>

        <div className="mt-3 flex gap-3">
          {/* Main Content Area */}
          <div className="flex-1 min-w-0">
            <div className="glass-panel rounded-xl overflow-hidden p-2 lg:p-3">
              <div className="mb-3 flex items-center overflow-x-auto whitespace-nowrap scrollbar-none rounded-lg border border-border bg-background/70 px-1.5 py-1.5 shadow-sm">
                <div className="flex gap-2">
                  {tabs.map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
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

                <div className={activeTab === "overview" ? "block" : "hidden"}>
                  <OverviewTab sampleId={id!} sample={sample} context={data} />
                </div>
                <div className={activeTab === "snvs" ? "block" : "hidden"}>
                  <VariantsTab sampleId={id!} />
                </div>
                <div className={activeTab === "cnvs" ? "block" : "hidden"}>
                  <CNVTab sampleId={id!} />
                </div>
                <div className={activeTab === "fusions" ? "block" : "hidden"}>
                  <FusionsTab sampleId={id!} />
                </div>
                <div className={activeTab === "translocations" ? "block" : "hidden"}>
                  <TranslocationsTab sampleId={id!} />
                </div>
                <div className={activeTab === "coverage" ? "block" : "hidden"}>
                  <CoverageTab sampleId={id!} />
                </div>
                <div className={activeTab === "reports" ? "block" : "hidden"}>
                  <ReportsTab sampleId={id!} />
                </div>
              </div>
            </div>
            {showComments && (
              <div className="mt-3">
                <CommentsPanel
                  sampleId={id!}
                  title="Sample Comments"
                  comments={data?.comments || sample?.comments || []}
                  queryKeys={[["sample", id]]}
                  allowGlobal={false}
                  suggestedText={data?.ai_text || data?.suggested_summary || ""}
                />
              </div>
            )}
          </div>
          
          {showFilters && (
            <FiltersSidebar sampleId={id!} sample={sample} context={data} activeTab={activeTab} />
          )}
        </div>
      </div>
    </div>
  )
}
