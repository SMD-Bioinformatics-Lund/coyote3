import { Layers, Network } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { SegmentedControl } from "@/components/ui/segmented-control"

export function SubpanelNavigation({ active }: { active: "definitions" | "associations" }) {
  const navigate = useNavigate()
  return (
    <SegmentedControl
      ariaLabel="Subpanel administration"
      className="w-full sm:w-fit"
      value={active}
      onValueChange={(value) => navigate(value === "definitions" ? "/admin/subpanels" : "/admin/assay-subpanels")}
      items={[
        { value: "definitions", label: <span className="inline-flex items-center gap-2"><Layers className="size-4 shrink-0" aria-hidden="true" />Definitions</span> },
        { value: "associations", label: <span className="inline-flex items-center gap-2"><Network className="size-4 shrink-0" aria-hidden="true" />Assay associations</span> },
      ]}
    />
  )
}
