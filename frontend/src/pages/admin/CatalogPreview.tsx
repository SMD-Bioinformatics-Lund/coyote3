import { useState } from "react"
import { PublicCatalogMatrix } from "../catalog/PublicCatalogMatrixPage"
import { PublicCatalog } from "../catalog/PublicCatalogPage"
import { PublicCatalogCompare } from "../catalog/PublicCatalogComparePage"
import type { Catalog } from "./catalog-types"
import { catalogPreviewIssue } from "./useCatalogDraftPreview"

export function CatalogPreview({ catalog }: { catalog: Catalog }) {
  const [view, setView] = useState<"catalog" | "matrix" | "compare">("catalog")
  const issue = catalogPreviewIssue(catalog)
  if (issue) return <section aria-label="Catalog preview" className="surface-panel space-y-2 p-4">
    <h2 className="type-section-title">{Object.keys(catalog.modalities).length ? "Complete the draft to preview" : "No published services"}</h2>
    <p role="status" className="type-body-sm text-muted-foreground">{issue}</p>
  </section>
  return <section aria-label="Catalog preview" className="min-w-0 bg-card text-card-foreground">
    {view === "matrix" ? <PublicCatalogMatrix previewDocument={catalog} onCatalog={() => setView("catalog")} />
      : view === "compare" ? <PublicCatalogCompare previewDocument={catalog} onCatalog={() => setView("catalog")} />
      : <PublicCatalog previewDocument={catalog} onMatrix={() => setView("matrix")} onCompare={() => setView("compare")} />}
  </section>
}
