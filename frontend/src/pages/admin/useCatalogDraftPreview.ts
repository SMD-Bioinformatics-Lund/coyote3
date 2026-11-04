import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Discovery } from "../catalog/offering-types"
import type { Catalog, Presentation } from "./catalog-types"
import { effectiveCatalogEntry } from "./catalog-hierarchy"

/** Identify unfinished prices before sending typed draft values to a schema boundary. */
export function catalogPriceIssue(catalog: Catalog): string | undefined {
  const issue = (value: Presentation, name: string) => value.price
    && (!/^\d+(?:\.\d{1,2})?$/.test(value.price.amount) || !/^[A-Z]{3}$/.test(value.price.currency))
    ? `Complete or cancel the price edit for ${name} before saving or previewing.` : undefined
  for (const section of Object.values(catalog.modalities)) {
    const sectionIssue = issue(section, section.title || section.label || "this section")
    if (sectionIssue) return sectionIssue
    for (const entry of Object.values(section.categories)) {
      const entryIssue = issue(entry, entry.title || entry.label || "this entry")
      if (entryIssue) return entryIssue
      for (const gene of entry.gene_lists || []) {
        const geneIssue = issue(gene, gene.label || "this gene list")
        if (geneIssue) return geneIssue
      }
    }
  }
}

/** Explain basic unfinished fields; the API remains authoritative for linked clinical scope. */
export function catalogPreviewIssue(catalog: Catalog): string | undefined {
  const price = catalogPriceIssue(catalog)
  if (price) return price
  if (!Object.keys(catalog.modalities).length) return "Add a section and an entry to preview the catalog."
  for (const section of Object.values(catalog.modalities)) {
    if (!section.label?.trim()) return "Give the new section a display name to preview the catalog."
    if (!Object.keys(section.categories).length) return `Add an entry or subsection to ${section.label} to preview the catalog.`
    for (const [key, entry] of Object.entries(section.categories)) {
      if (!entry.label?.trim()) return "Give every entry and subsection a display name to preview the catalog."
      const effective = effectiveCatalogEntry(section, key)
      if (entry.node_kind !== "folder" && (!effective.asp_id
        || !(effective.aspc_id || effective.aspc_ids?.production))) {
        return `Link an assay and production configuration for ${entry.label} to preview the catalog.`
      }
    }
  }
}

/** Debounce draft coverage and handle incomplete or rejected previews within the editor. */
export function useCatalogDraftPreview(catalog: Catalog) {
  const [document, setDocument] = useState(catalog)
  useEffect(() => {
    const timer = setTimeout(() => setDocument(catalog), 350)
    return () => clearTimeout(timer)
  }, [catalog])
  const incomplete = catalogPreviewIssue(catalog)
  const current = document === catalog && !incomplete
  const query = useQuery<Discovery>({
    queryKey: ["catalog-offering-preview", document],
    queryFn: ({ signal }) => api.post<Discovery>("/admin/assay-catalog/preview/offerings",
      { document }, { signal, errorNotice: "inline" }).then(response => response.data),
    enabled: Boolean(current), retry: false, gcTime: 30_000, refetchOnWindowFocus: false,
  })
  const validationError = query.error && "status" in query.error && query.error.status === 422
  const failure = query.isError ? validationError
    ? "Draft coverage is unavailable. Check the assay, production configuration and gene-list selections, then retry the preview."
    : "Could not refresh draft coverage. Your changes are retained; retry the preview when the service is available."
    : undefined
  return {
    data: current && !query.isFetching && !query.isError ? query.data : undefined,
    pending: !incomplete && (!current || query.isFetching),
    issue: incomplete || (current ? failure : undefined),
    canRetry: Boolean(current && query.isError),
    retry: () => void query.refetch(),
  }
}
