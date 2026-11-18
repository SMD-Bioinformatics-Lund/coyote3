// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
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
  return <Surface as="section" variant="panel" className="min-w-0 space-y-3 p-4" aria-label="Assay comparison">
    <h2 className="type-card-title">Compare published services</h2>
    <div role="region" aria-label="Service comparison, scroll horizontally" tabIndex={0}
      className="table-frame overflow-x-auto focus-visible:outline-2 focus-visible:outline-ring">
      <Table className="table-fixed"
        style={{ minWidth: `${12 + offerings.length * 18}rem` }}>
        <caption className="sr-only">Published service comparison</caption>
        <colgroup><col className="w-48" />{offerings.map(item => <col key={item.offering_id} />)}</colgroup>
        <TableHeader>
          <TableRow><TableHead scope="col" className="sticky left-0 border-r border-border bg-[var(--table-header-surface)]">Property</TableHead>
            {offerings.map(item => <TableHead scope="col" key={item.offering_id} className="border-r border-border align-top last:border-r-0">
              <span className="block">{item.assay_display_name || item.assay_label}</span>
              <span className="mt-1 block type-meta text-muted-foreground">{item.group_label} · {item.diagnosis_label}</span>
            </TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>{properties.map(property => <TableRow key={property}>
          <TableHead scope="row" className="sticky left-0 border-r border-border bg-card align-top font-semibold">{property}</TableHead>
          {offerings.map(item => <TableCell key={item.offering_id} className="break-words border-r border-border align-top last:border-r-0"><Value item={item} property={property} /></TableCell>)}
        </TableRow>)}</TableBody>
      </Table>
    </div>
  </Surface>
}
