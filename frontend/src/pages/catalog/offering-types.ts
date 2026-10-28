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
}
export type Discovery = { version: number; header: string; description: string; offerings: Offering[] }

export const familyLabels: Record<string, string> = {
  "panel-dna": "Targeted DNA panel", "panel-rna": "Targeted RNA panel",
  wes: "Whole exome sequencing", wgs: "Whole genome sequencing",
  wts: "Whole transcriptome sequencing",
}

export function offeringPrice(offering: Offering): string {
  if (!offering.price) return offering.pricing_message || "Contact for pricing"
  const { amount, currency, kind } = offering.price
  const value = new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount))
  return `${kind === "starting" ? "From " : kind === "estimated" ? "Estimated " : ""}${value}`
}

export function matchOffering(offering: Offering, query: string): string[] {
  const q = query.trim().toLocaleLowerCase()
  if (!q) return []
  const fields: [string, string[]][] = [
    ["Diagnosis", [offering.diagnosis_label, offering.diagnosis_id]],
    ["Test", [offering.title, offering.assay_id, offering.assay_label, offering.assay_display_name || ""]],
    ["Group", [offering.group_id, offering.group_label]],
    ["Method", [offering.modality, offering.family, familyLabels[offering.family] || offering.family]],
    ["Published gene scope", offering.gene_scopes.flatMap((scope) => scope.genes)],
  ]
  return fields.filter(([, values]) => values.some((value) => value.toLocaleLowerCase().includes(q)))
    .map(([label]) => label)
}
