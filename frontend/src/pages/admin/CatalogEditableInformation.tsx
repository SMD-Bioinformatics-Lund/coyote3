import type { ReactNode } from "react"
import { CatalogInformation, type CatalogEditableField } from "../catalog/CatalogInformation"
import { emptyCatalogInformation } from "../catalog/catalog-information"
import type { Offering } from "../catalog/offering-types"
import { CatalogInlineField } from "./CatalogInlineField"
import type { Category, Presentation, Workspace } from "./catalog-types"

/** Place draft field editors inside the same information panel used by the public catalog. */
export function CatalogEditableInformation({ value, effective, parentLabel, presets, offerings,
  onChange, editableFields, onAnalysisEditingChange, overview }: {
  value: Category; effective: Presentation; parentLabel?: string; presets: Workspace["presets"]
  offerings?: Offering[]; onChange: (patch: Partial<Category>) => void
  editableFields?: readonly CatalogEditableField[]
  onAnalysisEditingChange?: (editing: boolean) => void
  overview?: "home" | "dna" | "rna"
}) {
  const information = { ...emptyCatalogInformation(effective.title || effective.label || "New entry"),
    description: effective.description || "", subheading: effective.subheading || "",
    turnaround: effective.tat || "", analysis: effective.analysis || [],
    input_material: effective.input_material || [], sample_modes: effective.sample_modes || [],
    report_deliverables: effective.report_deliverables || [], clinical_indications: effective.clinical_indications || [],
    methodology: effective.methodology || "", limitations: effective.limitations || "",
    public_notes: effective.public_notes || "", ordering_information: effective.ordering_information || "",
    price: effective.price || null, pricing_message: effective.pricing_message || "",
  }
  const renderField = (field: CatalogEditableField, content: ReactNode) => {
    if (editableFields && !editableFields.includes(field)) return field === "subheading" ? null : content
    const keys = field === "price" ? ["price", "pricing_message"] : field === "title" ? ["label", "title"] : [field]
    return <CatalogInlineField key={field} field={field} value={value} effective={effective}
      parentLabel={field === "title" ? undefined : parentLabel} suppressed={value.clear_fields?.includes(field)} presets={presets}
      onEditingChange={field === "analysis" ? onAnalysisEditingChange : undefined}
      onChange={onChange} onInherit={parentLabel && field !== "title" ? () => onChange({
        ...Object.fromEntries(keys.map(key => [key, key === "price" ? null
          : ["analysis", "input_material", "sample_modes", "report_deliverables", "clinical_indications"].includes(key) ? [] : ""])),
        clear_fields: value.clear_fields?.filter(key => !keys.includes(key)),
      }) : undefined}>{content}</CatalogInlineField>
  }
  return <div className="space-y-4">
    <CatalogInformation information={information} offerings={offerings} overview={overview} renderField={renderField} />
    {overview && overview !== "home" && <details>
      <summary className="cursor-pointer type-body-sm font-semibold">Inherited service defaults</summary>
      <div className="mt-3"><CatalogInformation information={information} offerings={offerings}
        renderField={(field, content) => ["title", "subheading", "description"].includes(field) ? null : renderField(field, content)} /></div>
    </details>}
  </div>
}
