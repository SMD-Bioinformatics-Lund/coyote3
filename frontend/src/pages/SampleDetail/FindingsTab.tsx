import { SlidersHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { CNVTab } from "./CNVTab"
import { FusionsTab } from "./FusionsTab"
import { RnaAnalysisTab } from "./RnaAnalysisTabs"
import { TranslocationsTab } from "./TranslocationsTab"
import { VariantsTab } from "./VariantsTab"

export type FindingSectionId =
  | "snvs"
  | "germline-snvs"
  | "cnvs"
  | "fusions"
  | "rna-analysis"
  | "translocations"

type FindingSection = {
  id: FindingSectionId
  label: string
}

const FILTERABLE_SECTIONS = new Set<FindingSectionId>([
  "snvs",
  "germline-snvs",
  "cnvs",
  "fusions",
  "translocations",
])

function FindingPanel({
  section,
  sampleId,
  activeFilterSection,
  onSelectFilterSection,
}: {
  section: FindingSection
  sampleId: string
  activeFilterSection: FindingSectionId | null
  onSelectFilterSection: (section: FindingSectionId) => void
}) {
  const tableHeader = (
    <>
      <h2 id={`finding-section-${section.id}`} className="text-base font-semibold text-foreground">
        {section.label}
      </h2>
      {FILTERABLE_SECTIONS.has(section.id) && (
        <Button
          type="button"
          size="sm"
          variant={activeFilterSection === section.id ? "default" : "outline"}
          onClick={() => onSelectFilterSection(section.id)}
          aria-pressed={activeFilterSection === section.id}
        >
          <SlidersHorizontal className="h-4 w-4" />
          Filters
        </Button>
      )}
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

export function FindingsTab({
  sampleId,
  sections,
  activeFilterSection,
  onSelectFilterSection,
}: {
  sampleId: string
  sections: FindingSection[]
  activeFilterSection: FindingSectionId | null
  onSelectFilterSection: (section: FindingSectionId) => void
}) {
  return (
    <div className="space-y-6">
      {sections.map((section) => (
        <FindingPanel
          key={section.id}
          section={section}
          sampleId={sampleId}
          activeFilterSection={activeFilterSection}
          onSelectFilterSection={onSelectFilterSection}
        />
      ))}
    </div>
  )
}
