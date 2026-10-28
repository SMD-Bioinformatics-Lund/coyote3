import { Badge } from "@/components/ui/badge"
import { valueBadgeClass } from "@/lib/badge-colors"
import { BadgeList, HtmlText } from "./catalog-presentation"
import { familyLabels, offeringPrice, type Offering } from "./offering-types"
import { CatalogGeneMatches } from "./CatalogGeneMatches"

const properties = ["Method", "Analysis", "Gene scope", "Reports", "Price", "Limitations"] as const

function ComparisonValue({ item, property }: {
  item: Offering
  property: typeof properties[number]
}) {
  switch (property) {
    case "Method":
      return <Badge variant="outline" className={valueBadgeClass(item.family)}>
        {familyLabels[item.family] || item.family}
      </Badge>
    case "Analysis":
      return <BadgeList values={item.analysis} empty="Not specified" />
    case "Gene scope":
      return item.gene_scopes.length ? <ul className="space-y-2">
        {item.gene_scopes.map(scope => <li key={`${scope.list_id}:${scope.analysis}`}>
          <span className="font-semibold">{scope.analysis}</span>{" · "}
          <span className="type-numeric">{scope.genes.length}</span>{scope.genes.length === 1 ? " gene" : " genes"}
          <span className="mt-0.5 block type-meta text-muted-foreground">{scope.label}</span>
        </li>)}
      </ul> : <span className="text-muted-foreground">No published gene scope</span>
    case "Reports":
      return <BadgeList values={item.report_deliverables} empty="Not specified" />
    case "Price":
      return <span className={item.price ? "font-semibold type-numeric" : "text-muted-foreground"}>
        {offeringPrice(item)}
      </span>
    case "Limitations":
      return item.limitations ? <HtmlText html={item.limitations} />
        : <span className="text-muted-foreground">Not specified</span>
  }
}

export function CatalogComparisonTable({ offerings, genes = [] }: { offerings: Offering[]; genes?: readonly string[] }) {
  return <section className="surface-panel min-w-0 space-y-3 p-4" aria-labelledby="catalog-comparison-title">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="catalog-comparison-title" className="type-section-title">Compare published services</h2>
      <Badge variant="outline">{offerings.length} services</Badge>
    </div>
    <div className="paper-surface min-w-0 max-w-full overflow-hidden rounded-lg [contain:paint]">
      <div className="max-w-full overflow-x-auto overscroll-x-contain focus-visible:outline-2 focus-visible:outline-ring"
        role="region" aria-label="Service comparison, scroll horizontally to view all services" tabIndex={0}>
        <table className="type-table-cell w-full table-fixed border-separate border-spacing-0 text-left type-numeric"
          style={{ minWidth: `${10 + offerings.length * 16}rem` }}>
          <caption className="sr-only">Published service comparison</caption>
          <colgroup><col className="w-40" />{offerings.map(item => <col key={item.offering_id} />)}</colgroup>
          <thead className="type-table-header bg-[var(--table-header-surface)]">
            <tr>
              <th scope="col" className="sticky left-0 z-20 border-b-2 border-r border-border bg-[var(--table-header-surface)] px-4 py-4 align-bottom">Property</th>
              {offerings.map(item => <th key={item.offering_id} scope="col" title={item.assay_display_name || item.title}
                className={`border-b-2 border-r border-t-4 border-border px-4 py-4 align-top last:border-r-0 ${item.modality === "rna" ? "border-t-rna bg-rna/8" : "border-t-dna bg-dna/8"}`}>
                <div className="mb-2 flex flex-wrap gap-2">
                  <Badge variant="outline" className={valueBadgeClass(item.modality)}>{item.modality.toUpperCase()}</Badge>
                  <span className="type-meta text-muted-foreground">{item.diagnosis_label}</span>
                </div>
                <span className="block type-body-sm font-semibold break-words">{item.assay_label || item.assay_id}</span>
              </th>)}
            </tr>
          </thead>
          <tbody>
            {genes.length > 0 && <tr className="bg-primary/5">
              <th scope="row" className="sticky left-0 border-b border-r border-border bg-card px-4 py-3 align-top font-semibold">Requested genes</th>
              {offerings.map(item => <td key={item.offering_id} className="border-b border-r border-border px-4 py-3 align-top"><CatalogGeneMatches offering={item} genes={genes} /></td>)}
            </tr>}
            {properties.map(property => <tr key={property}
              className="odd:bg-[var(--paper-raised)] even:bg-table-row-alt hover:bg-primary/5">
              <th scope="row" className="sticky left-0 z-10 border-b border-r border-border/60 bg-inherit px-4 py-3 align-top font-semibold">{property}</th>
              {offerings.map(item => <td key={item.offering_id}
                className="border-b border-r border-border/60 px-4 py-3 align-top break-words last:border-r-0">
                <ComparisonValue item={item} property={property} />
              </td>)}
            </tr>)}
          </tbody>
        </table>
      </div>
    </div>
  </section>
}
