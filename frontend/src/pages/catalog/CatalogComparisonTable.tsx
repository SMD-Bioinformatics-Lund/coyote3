import { BadgeList, HtmlText } from "./catalog-presentation"
import { publishedGeneCount } from "./catalog-information"
import { offeringPrice, type Offering } from "./offering-types"

const properties = ["Description", "Method", "Price", "Turnaround", "Analyses", "Sample types",
  "Sample modes", "Published covered genes", "Assay covered genes", "Platform", "Read length",
  "Reporting", "Limitations", "Ordering information"] as const

function Value({ item, property }: { item: Offering; property: typeof properties[number] }) {
  switch (property) {
    case "Description": return <HtmlText html={item.description || "Not specified"} />
    case "Method": return <span>{item.modality.toUpperCase()} · {item.family}</span>
    case "Price": return <><span>{offeringPrice(item)}</span>{item.price?.conditions && <p className="mt-1 type-meta text-muted-foreground">{item.price.conditions}</p>}</>
    case "Turnaround": return <span>{item.turnaround || "Not specified"}</span>
    case "Analyses": return <BadgeList values={item.analysis} empty="Not specified" />
    case "Sample types": return <BadgeList values={item.input_material} empty="Not specified" />
    case "Sample modes": return <BadgeList values={item.sample_modes} empty="Not specified" />
    case "Published covered genes": return <span>{publishedGeneCount([item])}</span>
    case "Assay covered genes": return <span>{item.covered_gene_count ?? "Not specified"}</span>
    case "Platform": return <span>{item.platform || "Not specified"}</span>
    case "Read length": return <span>{item.read_length == null ? "Not specified" : `${item.read_length} bp${item.read_mode ? ` · ${item.read_mode}` : ""}`}</span>
    case "Reporting": return <BadgeList values={item.report_deliverables} empty="Not specified" />
    case "Limitations": return <HtmlText html={item.limitations || "Not specified"} />
    case "Ordering information": return <HtmlText html={item.ordering_information || "Not specified"} />
  }
}

/** Align each service property across the selected reviewed assay/diagnosis scopes. */
export function CatalogComparisonTable({ offerings }: { offerings: Offering[] }) {
  return <section className="surface-panel min-w-0 space-y-3 p-4" aria-label="Assay comparison">
    <h2 className="type-section-title">Compare published services</h2>
    <div role="region" aria-label="Service comparison, scroll horizontally" tabIndex={0}
      className="max-w-full overflow-x-auto rounded-lg border border-border focus-visible:outline-2 focus-visible:outline-ring">
      <table className="w-full table-fixed border-collapse text-left type-body-sm"
        style={{ minWidth: `${12 + offerings.length * 18}rem` }}>
        <caption className="sr-only">Published service comparison</caption>
        <colgroup><col className="w-48" />{offerings.map(item => <col key={item.offering_id} />)}</colgroup>
        <thead className="bg-[var(--table-header-surface)]">
          <tr><th scope="col" className="sticky left-0 border-b border-r border-border bg-[var(--table-header-surface)] p-3">Property</th>
            {offerings.map(item => <th scope="col" key={item.offering_id} className="border-b border-r border-border p-3 align-top last:border-r-0">
              <span className="block">{item.assay_display_name || item.assay_label}</span>
              <span className="mt-1 block type-meta text-muted-foreground">{item.group_label} · {item.diagnosis_label}</span>
            </th>)}
          </tr>
        </thead>
        <tbody>{properties.map(property => <tr key={property}>
          <th scope="row" className="sticky left-0 border-b border-r border-border bg-card p-3 align-top font-semibold">{property}</th>
          {offerings.map(item => <td key={item.offering_id} className="break-words border-b border-r border-border p-3 align-top last:border-r-0"><Value item={item} property={property} /></td>)}
        </tr>)}</tbody>
      </table>
    </div>
  </section>
}
