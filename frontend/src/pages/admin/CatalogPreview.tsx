import { useState } from "react"
import { PublicCatalogMatrix } from "../catalog/PublicCatalogMatrixPage"
import { PublicCatalog } from "../catalog/PublicCatalogPage"
import type { Catalog } from "./catalog-types"

export function CatalogPreview({ catalog }: { catalog: Catalog }) {
  const [matrix, setMatrix] = useState(false)
  return <section aria-label="Catalog preview" className="min-w-0 bg-card text-card-foreground">
    {matrix ? <PublicCatalogMatrix previewDocument={catalog} onCatalog={() => setMatrix(false)} />
      : <PublicCatalog previewDocument={catalog} onMatrix={() => setMatrix(true)} />}
  </section>
}
