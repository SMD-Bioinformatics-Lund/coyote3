export type GeneScope = {
  list_id: string; label: string; revision: number; analysis: string
  genes: string[]; excluded_gene_count: number
}
export type Offering = {
  offering_id: string; title: string; group_id: string; group_label: string
  diagnosis_id: string; diagnosis_label: string; modality: "dna" | "rna"
  family: string; assay_id: string; assay_label: string; assay_display_name?: string; description: string
  analysis: string[]; price: { amount: string; currency: string; kind: "fixed" | "starting" | "estimated"; conditions: string } | null
  pricing_message: string; turnaround: string; input_material: string[]
  report_deliverables: string[]; methodology: string; limitations: string
  ordering_information: string; gene_scopes: GeneScope[]
  sample_modes?: string[]; platform?: string; read_length?: number | null; read_mode?: string
  covered_gene_count?: number | null
}
export type CatalogNavigationNode = {
  node_id: string; parent_id: string | null; offering_id: string | null
  label: string; title: string; description: string; subheading: string
  input_material: string[]; sample_modes: string[]; analysis: string[]; turnaround: string
  report_deliverables: string[]; clinical_indications: string[]; limitations: string
  public_notes: string; methodology: string; ordering_information: string
  price?: Offering["price"]; pricing_message?: string; clear_fields?: string[]
}
export type Discovery = {
  version: number; header: string; description: string; offerings: Offering[]
  navigation: CatalogNavigationNode[]
}

export function offeringPrice(offering: Pick<Offering, "price" | "pricing_message">): string {
  if (!offering.price) return offering.pricing_message || "Contact for pricing"
  const { amount, currency, kind } = offering.price
  if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || !/^[A-Z]{3}$/.test(currency)) return "Price not complete"
  const value = new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount))
  return `${kind === "starting" ? "From " : kind === "estimated" ? "Estimated " : ""}${value}`
}
