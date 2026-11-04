import type { CatalogNavigationNode, Offering } from "./offering-types"

/** Create a presentation without implying any service capabilities or gene coverage. */
export function emptyCatalogInformation(title: string): CatalogNavigationNode {
  return { node_id: "overview", parent_id: null, offering_id: null, label: title, title,
    description: "", subheading: "", input_material: [], sample_modes: [], analysis: [],
    turnaround: "", report_deliverables: [], clinical_indications: [], limitations: "",
    public_notes: "", methodology: "", ordering_information: "", price: null, pricing_message: "" }
}

/** Fill missing descriptive fields from the immediate parent, respecting explicit suppression. */
export function inheritCatalogInformation(child: CatalogNavigationNode,
  parent?: CatalogNavigationNode): CatalogNavigationNode {
  if (!parent) return child
  const fields = ["description", "subheading", "input_material", "sample_modes", "analysis",
    "turnaround", "report_deliverables", "clinical_indications", "limitations", "public_notes",
    "methodology", "ordering_information", "price", "pricing_message"] as const
  return { ...child, ...Object.fromEntries(fields.map(field => {
    const value = child[field]
    const suppressed = child.clear_fields?.includes(field === "turnaround" ? "tat" : field)
    const missing = value == null || value === "" || Array.isArray(value) && !value.length
    return [field, missing && !suppressed ? parent[field] : value]
  })) }
}

/** Resolve service wording without substituting another diagnosis's capabilities or genes. */
export function offeringInformation(item: Offering, source?: CatalogNavigationNode,
  parent?: CatalogNavigationNode): CatalogNavigationNode {
  const inherited = inheritCatalogInformation(source || emptyCatalogInformation(item.title), parent)
  const local: CatalogNavigationNode = { ...emptyCatalogInformation(item.title), ...item,
    sample_modes: item.sample_modes || [], clear_fields: source?.clear_fields,
    node_id: item.offering_id, offering_id: item.offering_id,
  }
  const result = inheritCatalogInformation(local, inherited)
  return { ...result, title: source?.title || item.title, analysis: item.analysis }
}

/** Count distinct genes in the reviewed effective scope, never the live assay definition. */
export function publishedGeneCount(offerings: readonly Offering[]): number {
  return new Set(offerings.flatMap(item => item.gene_scopes.flatMap(scope => scope.genes))).size
}

/** Attach resolved public wording for summaries while retaining each frozen gene scope. */
export function catalogService(item: Offering, source?: CatalogNavigationNode,
  parent?: CatalogNavigationNode): Offering {
  const information = offeringInformation(item, source, parent)
  return { ...item, description: information.description, turnaround: information.turnaround,
    input_material: information.input_material, sample_modes: information.sample_modes,
    report_deliverables: information.report_deliverables, methodology: information.methodology,
    limitations: information.limitations, ordering_information: information.ordering_information,
    price: information.price || null, pricing_message: information.pricing_message || item.pricing_message }
}
