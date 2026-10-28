import { icon } from "@/lib/assets"
import { useNavigate } from "react-router-dom"
import { SegmentedControl } from "@/components/ui/segmented-control"

export function DiagnosisNavigation({ active }: { active: "definitions" | "associations" }) {
  const navigate = useNavigate()
  return (
    <SegmentedControl
      ariaLabel="Diagnosis administration"
      className="w-full sm:w-fit"
      value={active}
      onValueChange={(value) => navigate(value === "definitions" ? "/admin/diagnoses" : "/admin/assay-diagnoses")}
      items={[
        { value: "definitions", label: <span className="inline-flex items-center gap-2"><icon.layers className="size-4 shrink-0" aria-hidden="true" />Definitions</span> },
        { value: "associations", label: <span className="inline-flex items-center gap-2"><icon.network className="size-4 shrink-0" aria-hidden="true" />Assay associations</span> },
      ]}
    />
  )
}
