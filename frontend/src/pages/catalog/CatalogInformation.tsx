import type { ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { valueBadgeClass } from "@/lib/badge-colors"
import { BadgeList, HtmlText } from "./catalog-presentation"
import { offeringPrice, type CatalogNavigationNode, type Offering } from "./offering-types"
import { publishedGeneCount } from "./catalog-information"

export type CatalogEditableField = "title" | "subheading" | "description" | "price" | "tat"
  | "analysis" | "input_material" | "sample_modes" | "report_deliverables"
  | "clinical_indications" | "methodology" | "limitations" | "ordering_information" | "public_notes"

const methodLabels: Record<string, string> = {
  wgs: "Whole genome sequencing", wts: "Whole transcriptome sequencing",
  "panel-dna": "Targeted DNA panels", "panel-rna": "Targeted RNA panels",
}

/** Keep the selected scope's service facts together, before its gene tables. */
export function CatalogInformation({ information, offerings = [], renderField, overview }: {
  information: CatalogNavigationNode; offerings?: Offering[]
  renderField?: (field: CatalogEditableField, content: ReactNode) => ReactNode
  overview?: "home" | "dna" | "rna"
}) {
  const modalities = [...new Set(offerings.map(item => item.modality))]
  const families = [...new Set(offerings.map(item => item.family))]
  const modality = overview === "dna" || overview === "rna" ? overview
    : !overview && modalities.length === 1 ? modalities[0] : undefined
  const family = !overview && families.length === 1 ? families[0] : undefined
  const field = (key: CatalogEditableField, content: ReactNode) => renderField ? renderField(key, content) : content
  const heading = <header className="space-y-2">
    {field("title", <h2 className="catalog-information-title type-page-title break-words text-primary">{information.title}</h2>)}
    {(information.subheading || renderField) && field("subheading",
      <p className="type-section-title">{information.subheading || "Add a subheading"}</p>)}
  </header>
  if (overview) {
    const copy = {
      home: "Explore sequencing-based assays for the analysis of somatic alterations in cancer. The catalog brings together available methods, clinical applications and the published gene scopes for each service.",
      dna: "DNA sequencing services assess genomic alterations in cancer. Explore the available sequencing methods, clinical groups and diagnoses to find the relevant service and its published scope.",
      rna: "RNA sequencing services investigate expressed transcripts and gene fusions in cancer. Explore the available sequencing methods, clinical groups and diagnoses to find the relevant service and its published scope.",
    }[overview]
    const methods = [...new Set(offerings.map(item => item.family))]
    return <section aria-label="Catalog overview" data-modality={modality}
      className={`surface-panel ${modality ? "catalog-service-card" : ""} catalog-information min-w-0 space-y-5 p-4 sm:p-5`}>
      {heading}
      {field("description", <HtmlText html={information.description || (renderField ? "Add a description" : "")} className="type-body leading-relaxed" />)}
      <p className="type-body leading-relaxed">{copy}</p>
      <div className="content-item space-y-3 p-4">
        <h3 className="catalog-information-title type-card-title text-primary">Find the right service</h3>
        <p className="type-body-sm leading-relaxed">Browse the levels on the left to read about specimen requirements, analyses, turnaround times and pricing. Each diagnosis includes its service information, followed by the covered genes. Use Compare assays to view services side by side.</p>
        {methods.length > 0 && <div className="flex flex-wrap gap-2">{methods.map(method =>
          <Badge key={method} variant="outline" className={valueBadgeClass(method)}>
            {methodLabels[method] || method}
          </Badge>)}</div>}
      </div>
    </section>
  }
  const union = (local: string[], read: (item: Offering) => string[] | undefined) =>
    [...new Set([...local, ...offerings.flatMap(item => read(item) || [])])]
  const fact = (value: string, kind?: string) => {
    const essential = kind === "price" || kind === "turnaround"
    return kind && (essential || value !== "Not specified")
      ? <Badge variant="outline" data-kind={kind}
        className={`catalog-fact-badge ${essential ? "catalog-essential-badge" : ""} max-w-full whitespace-normal break-words text-left`}>
        {essential && <span className="type-label">{kind === "price" ? "Price" : "Turnaround (TAT)"}</span>}
        <span className={essential ? "type-card-title font-semibold" : undefined}>{value}</span>
      </Badge> : value
  }
  const variants = (read: (item: Offering) => string, fallback = "", kind?: string): ReactNode => {
    const grouped = new Map<string, string[]>()
    for (const item of offerings) {
      const value = read(item) || fallback || "Not specified"
      const names = grouped.get(value) || []
      names.push(`${item.assay_label} · ${item.diagnosis_label}`)
      grouped.set(value, names)
    }
    if (!grouped.size) return fact(fallback || "Not specified", kind)
    if (grouped.size === 1 && (!fallback || grouped.has(fallback))) return fact([...grouped.keys()][0], kind)
    return <div className="space-y-2">
      {fallback && !grouped.has(fallback) && <p>{fact(fallback, kind)}</p>}
      <ul className="space-y-1">{[...grouped].map(([value, names]) =>
        <li key={value}><span className="font-semibold">{[...new Set(names)].join(", ")}</span>: {fact(value, kind)}</li>)}</ul>
    </div>
  }
  const descriptions = [...new Set([information.description, ...offerings.map(item => item.description)].filter(Boolean))]
  const coveredGenes = publishedGeneCount(offerings)
  const price = variants(item => offeringPrice({ ...item,
    price: item.price || information.price || null,
    pricing_message: item.pricing_message || information.pricing_message || "Contact for pricing" }),
    information.price ? offeringPrice({ price: information.price, pricing_message: "" }) : information.pricing_message, "price")
  const turnaround = variants(item => item.turnaround, information.turnaround, "turnaround")
  const rows: { label: string; value: ReactNode; field?: CatalogEditableField }[] = [
    { label: "Available analyses", field: "analysis", value: <BadgeList values={union(offerings.length ? [] : information.analysis, item => item.analysis)} tone="primary" empty="Not specified" /> },
    { label: "Sample types / input material", field: "input_material", value: <BadgeList values={union(information.input_material, item => item.input_material)} kind="material" tone="secondary" empty="Not specified" /> },
    { label: "Sample modes", field: "sample_modes", value: <BadgeList values={union(information.sample_modes, item => item.sample_modes)} tone="primary" empty="Not specified" /> },
    { label: "Published covered genes", value: offerings.length
      ? fact(`${coveredGenes} unique ${coveredGenes === 1 ? "gene" : "genes"} in the published scope`, "coverage") : "Not specified" },
    { label: "Platform", value: variants(item => item.platform || "", "", "platform") },
    { label: "Read length", value: variants(item => item.read_length == null ? ""
      : `${item.read_length} bp${item.read_mode ? ` · ${item.read_mode}` : ""}`, "", "read") },
    { label: "Reporting", field: "report_deliverables", value: <BadgeList values={union(information.report_deliverables, item => item.report_deliverables)} tone="primary" empty="Not specified" /> },
  ]
  if (offerings.some(item => item.covered_gene_count != null)) rows.push({
    label: "Assay covered genes", value: variants(item => item.covered_gene_count == null ? "" : String(item.covered_gene_count), "", "coverage"),
  })
  if (information.clinical_indications.length || renderField) rows.push({ label: "Clinical indications", field: "clinical_indications",
    value: <BadgeList values={information.clinical_indications} /> })
  for (const [label, field, value, alternatives] of [
    ["Methodology", "methodology", information.methodology, offerings.map(item => item.methodology)],
    ["Analytical limitations", "limitations", information.limitations, offerings.map(item => item.limitations)],
    ["Ordering information", "ordering_information", information.ordering_information, offerings.map(item => item.ordering_information)],
    ["Public notes", "public_notes", information.public_notes, []],
  ] as const) {
    const texts = value ? [value] : [...new Set(alternatives.filter(Boolean))]
    if (texts.length || renderField) rows.push({ label, field, value: texts.length
      ? <div className="space-y-2">{texts.map(text => <HtmlText key={text} html={text} />)}</div> : "Not specified" })
  }
  const conditions = [...new Set([information.price?.conditions, ...offerings.map(item => item.price?.conditions)].filter(Boolean))]
  return <section data-modality={modality} data-family={family}
    className={`surface-panel ${modality ? "catalog-service-card" : ""} catalog-information min-w-0 space-y-4 p-4 sm:p-5`} aria-label="Service information">
    <div className="catalog-information-heading flex min-w-0 flex-col items-start gap-4 xl:flex-row xl:justify-between">
      <div className="min-w-0 flex-1">{heading}</div>
      <div role="group" aria-label="Service essentials"
        className="flex min-w-0 max-w-full flex-wrap items-start gap-3 break-words type-body-sm xl:max-w-[60%] xl:justify-end">
        <div className="min-w-0 max-w-full">{field("price", price)}</div>
        <div className="min-w-0 max-w-full">{field("tat", turnaround)}</div>
      </div>
    </div>
    {offerings.length > 0 && <div className="flex flex-wrap gap-2">
      {[...new Set(offerings.flatMap(item => [item.modality, item.family, item.group_label]))].map(value =>
        <Badge key={value} variant="outline" className={valueBadgeClass(value)}>
          {value === "dna" ? "DNA sequencing" : value === "rna" ? "RNA sequencing" : methodLabels[value] || value}
        </Badge>)}
    </div>}
    {renderField ? renderField("description", <HtmlText html={information.description || "Add a description"} className="type-body leading-relaxed" />)
      : <div className="space-y-3">{descriptions.map(text => <div key={text} className="space-y-1">
      {descriptions.length > 1 && text !== information.description && <p className="type-label text-muted-foreground">
        {[...new Set(offerings.filter(item => item.description === text).map(item => `${item.assay_label} · ${item.diagnosis_label}`))].join(", ")}
      </p>}
      <HtmlText html={text} className="type-body leading-relaxed" />
    </div>)}</div>}
    <dl className="grid gap-x-8 lg:grid-cols-2">
      {rows.map(({ label, value, field: key }) => <div key={label}
        data-fact={key || (label === "Published covered genes" ? "coverage" : undefined)}
        className={`catalog-information-fact min-w-0 space-y-2 border-t border-border py-3 ${label === "Published covered genes" ? "catalog-information-highlight" : ""}`}>
        <dt className="type-label font-semibold text-primary">{label}</dt>
        <dd className="min-w-0 break-words type-body-sm">{key ? field(key, value) : value}</dd>
      </div>)}
    </dl>
    {conditions.map(text => <p key={text} className="type-meta text-muted-foreground">{text}</p>)}
    <p className="type-meta text-muted-foreground">Gene counts use reviewed published scopes. Overview values cover the services in this selection; individual services may differ. Different prices and turnaround times are listed by assay and diagnosis.</p>
  </section>
}
