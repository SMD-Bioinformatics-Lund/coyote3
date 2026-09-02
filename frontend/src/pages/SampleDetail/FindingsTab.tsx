import { ChevronLeft, Filter } from "lucide-react"
import { useState } from "react"
import { CNVTab } from "./CNVTab"
import { FusionsTab } from "./FusionsTab"
import { RnaAnalysisTab } from "./RnaAnalysisTabs"
import { TranslocationsTab } from "./TranslocationsTab"
import { VariantsTab } from "./VariantsTab"
import { CollapsedFiltersRail, FiltersSidebar } from "./FiltersSidebar"

export type FindingSectionId =
  | "snvs"
  | "germline-snvs"
  | "cnvs"
  | "fusions"
  | "rna-analysis"
  | "translocations"

export type FindingSection = {
  id: FindingSectionId
  label: string
}

export type AnalysisFilterSection = {
  id: string
  label: string
}

export const FILTERABLE_ANALYSIS_SECTIONS = new Set([
  "snvs",
  "germline-snvs",
  "cnvs",
  "fusions",
  "translocations",
  "coverage",
])

function FindingPanel({
  section,
  sampleId,
}: {
  section: FindingSection
  sampleId: string
}) {
  const tableHeader = (
    <>
      <h2 id={`finding-section-${section.id}`} className="text-base font-semibold text-foreground">
        {section.label}
      </h2>
    </>
  )

  return (
    <section aria-labelledby={`finding-section-${section.id}`} className="scroll-mt-4">
      {section.id === "snvs" && <VariantsTab sampleId={sampleId} intent="somatic" header={tableHeader} />}
      {section.id === "germline-snvs" && <VariantsTab sampleId={sampleId} intent="germline" header={tableHeader} />}
      {section.id === "cnvs" && <CNVTab sampleId={sampleId} header={tableHeader} />}
      {section.id === "fusions" && <FusionsTab sampleId={sampleId} header={tableHeader} />}
      {section.id === "rna-analysis" && <RnaAnalysisTab sampleId={sampleId} header={tableHeader} />}
      {section.id === "translocations" && <TranslocationsTab sampleId={sampleId} header={tableHeader} />}
    </section>
  )
}

export function ClassicAnalysisFiltersSidebar({
  sampleId,
  sample,
  context,
  sections,
}: {
  sampleId: string
  sample: any
  context?: any
  sections: AnalysisFilterSection[]
}) {
  const [isCollapsed, setIsCollapsed] = useState(true)
  const filterableSections = sections.filter((section) => FILTERABLE_ANALYSIS_SECTIONS.has(section.id))
  if (filterableSections.length === 0) return null

  if (isCollapsed) {
    return (
      <div className="sticky top-3 max-h-[calc(100dvh-2rem)]" aria-label="All finding filters">
        <CollapsedFiltersRail
          label="Finding filters"
          onExpand={() => setIsCollapsed(false)}
          ariaLabel="Expand finding filters"
        />
      </div>
    )
  }

  return (
    <aside aria-label="All finding filters" className="sticky top-3 flex max-h-[calc(100dvh-2rem)] w-72 shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <Filter className="h-4 w-4 text-primary" />
        <div>
          <h2 className="type-card-title">Finding filters</h2>
          <p className="type-meta text-muted-foreground">All enabled analysis filters</p>
        </div>
        <button
          type="button"
          onClick={() => setIsCollapsed(true)}
          className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Collapse finding filters"
          aria-label="Collapse finding filters"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 space-y-3 overflow-y-auto p-2.5 scrollbar-thin scrollbar-thumb-border">
        {filterableSections.map((section) => (
          <FiltersSidebar
            key={section.id}
            inline
            embedded
            sampleId={sampleId}
            sample={sample}
            context={context}
            activeTab={section.id}
            intent={section.id === "germline-snvs" ? "germline" : "somatic"}
          />
        ))}
      </div>
    </aside>
  )
}

export function FindingsTab({
  sampleId,
  sections,
}: {
  sampleId: string
  sections: FindingSection[]
}) {
  return (
    <div className="space-y-6">
      {sections.map((section) => (
        <FindingPanel
          key={section.id}
          section={section}
          sampleId={sampleId}
        />
      ))}
    </div>
  )
}
