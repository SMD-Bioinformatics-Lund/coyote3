import { expect, it } from "vitest"
import { addCatalogChild, addCatalogParentDefaults, catalogEditorNavigation } from "./catalog-editor-navigation"
import { effectiveCatalogEntry } from "./catalog-hierarchy"
import type { Catalog, SourceOptions } from "./catalog-types"

const sources: SourceOptions = {
  asps: [{ asp_id: "hema", label: "HEM", category: "dna", family: "panel-dna", group: "hematology", group_label: "Hematology" }],
  aspcs: [{ asp_id: "hema", aspc_id: "hema-mpn", diagnosis_id: "mpn", diagnosis_label: "MPN" }], gene_lists: [],
}
const catalog: Catalog = { header: "Synthetic catalog", description: "", layout: { order: ["dna"] },
  modalities: { dna: { label: "DNA", omics: "dna", tat: "21 days", categories: {
    old: { label: "Other defaults", node_kind: "folder", asp_id: "hema", aspc_id: "hema-mpn",
      tat: "7 days", analysis: ["SNV"], gene_lists: [{ isgl_id: "genes", analysis: ["SNV"] }] },
    mpn: { label: "Synthetic HEM / MPN", parent_key: "old", catalog_id: "published-mpn" },
  } } },
}

it("uses the public modality/method/group/diagnosis levels for flat and inherited bindings", () => {
  const nodes = catalogEditorNavigation(catalog, sources)
  expect(nodes.filter(node => node.node_id.startsWith("[") && !node.target?.entry).map(node => node.label))
    .toEqual(["DNA", "Panels", "Hematology", "MPN"])
  expect(nodes.find(node => node.target?.entry === "mpn")?.target)
    .toEqual(expect.objectContaining({ section: "dna", entry: "mpn" }))
})

it("creates editable parent defaults without changing existing effective service scope", () => {
  const before = JSON.stringify(catalog)
  const nodes = catalogEditorNavigation(catalog, sources)
  const group = nodes.find(node => node.level === "group")!
  const result = addCatalogParentDefaults(catalog, group, nodes)
  const value = result.catalog.modalities.dna.categories[result.target.entry]
  expect(value.label).toBe("Hematology")
  expect(value.node_kind).toBe("folder")
  expect(result.catalog.modalities.dna.categories.mpn.catalog_id).toBe("published-mpn")
  const old = effectiveCatalogEntry(catalog.modalities.dna, "mpn")
  const updated = effectiveCatalogEntry(result.catalog.modalities.dna, "mpn")
  for (const field of ["asp_id", "aspc_id", "analysis", "gene_lists", "tat"] as const) {
    expect(updated[field]).toEqual(old[field])
  }
  expect(JSON.stringify(catalog)).toBe(before)
  const refreshed = catalogEditorNavigation(result.catalog, sources)
  expect(refreshed.find(node => node.level === "group")?.target).toEqual(result.target)
  const renamed = structuredClone(result.catalog)
  renamed.modalities.dna.categories[result.target.entry].title = "Hematology service information"
  expect(catalogEditorNavigation(renamed, sources).find(node => node.level === "group")?.target).toEqual(result.target)
})

it("preserves inherited empty fields when adding shared defaults", () => {
  const draft = structuredClone(catalog)
  draft.modalities.dna.analysis = ["CNV"]
  draft.modalities.dna.price = { amount: "100", currency: "SEK", kind: "fixed", conditions: "" }
  draft.modalities.dna.categories.panels = { label: "Panels", node_kind: "folder",
    gene_lists: [{ isgl_id: "parent-genes", analysis: ["CNV"] }],
    aspc_ids: { production: "hema-mpn" } }
  draft.modalities.dna.categories.old.parent_key = "panels"
  draft.modalities.dna.categories.old.clear_fields = ["tat", "analysis", "gene_lists", "price", "aspc_ids"]
  delete draft.modalities.dna.categories.old.tat
  delete draft.modalities.dna.categories.old.analysis
  delete draft.modalities.dna.categories.old.gene_lists
  const before = effectiveCatalogEntry(draft.modalities.dna, "mpn")
  const nodes = catalogEditorNavigation(draft, sources)
  const result = addCatalogParentDefaults(draft, nodes.find(node => node.level === "group")!, nodes)
  const saved: Catalog = JSON.parse(JSON.stringify(result.catalog))
  const after = effectiveCatalogEntry(saved.modalities.dna, "mpn")
  for (const field of ["tat", "analysis", "gene_lists", "price", "aspc_ids"] as const) {
    expect(after[field]).toEqual(before[field])
  }
  expect(draft.modalities.dna.categories.mpn.clear_fields).toBeUndefined()
})

it("keeps mismatched configuration bindings editable without assigning them to a clinical branch", () => {
  const mismatched = { ...sources, aspcs: [{ ...sources.aspcs[0], asp_id: "another-assay" }] }
  const nodes = catalogEditorNavigation(catalog, mismatched)
  expect(nodes.flatMap(node => node.offerings)).toEqual([])
  expect(nodes.find(node => node.target?.entry === "mpn")?.target)
    .toEqual(expect.objectContaining({ section: "dna", entry: "mpn" }))
})

it("keeps separate assay entries editable beneath their custom authoring parent", () => {
  const draft = structuredClone(catalog)
  draft.modalities.dna.categories.second = { ...draft.modalities.dna.categories.mpn,
    catalog_id: "second", label: "Second service" }
  const nodes = catalogEditorNavigation(draft, sources)
  const parent = nodes.find(node => node.target?.entry === "old")!
  expect(nodes.filter(node => node.parent_id === parent.node_id).map(node => node.target?.entry))
    .toEqual(["mpn", "second"])
})

it("keeps a newly attached assay beneath its custom section without a second source tree", () => {
  const draft = structuredClone(catalog)
  draft.modalities.custom = { label: "Custom section", omics: "dna", categories: {
    service: { label: "Named service", asp_id: "hema", aspc_id: "hema-mpn", diagnosis_id: "mpn" },
  } }
  const nodes = catalogEditorNavigation(draft, sources)
  const section = nodes.find(node => node.target?.section === "custom" && !node.target.entry)!
  const services = nodes.filter(node => node.target?.section === "custom" && node.target.entry === "service")
  expect(services).toHaveLength(1)
  expect(services[0].parent_id).toBe(section.node_id)
  expect(services[0].label).toBe("Named service")
})

it("adds a subsection and child beneath a virtual parent without changing existing scope", () => {
  const before = structuredClone(catalog)
  const nodes = catalogEditorNavigation(catalog, sources)
  const parent = addCatalogParentDefaults(catalog, nodes.find(node => node.level === "group")!, nodes)
  const folder = addCatalogChild(parent.catalog, parent.target, "folder")
  const child = addCatalogChild(folder.catalog, folder.target, "entry")
  expect(folder.catalog.modalities.dna.categories[folder.target.entry])
    .toEqual(expect.objectContaining({ node_kind: "folder", parent_key: parent.target.entry }))
  expect(child.catalog.modalities.dna.categories[child.target.entry].parent_key).toBe(folder.target.entry)
  expect(child.catalog.modalities.dna.categories.mpn).toEqual(parent.catalog.modalities.dna.categories.mpn)
  expect(effectiveCatalogEntry(child.catalog.modalities.dna, "mpn"))
    .toEqual(effectiveCatalogEntry(parent.catalog.modalities.dna, "mpn"))
  expect(catalog).toEqual(before)
})

it("turns an unbound parent into a section when a child is added", () => {
  const draft = structuredClone(catalog)
  draft.modalities.dna.categories.empty = { label: "New section", node_kind: "entry" }
  const result = addCatalogChild(draft, { section: "dna", entry: "empty" }, "entry")
  expect(result.catalog.modalities.dna.categories.empty.node_kind).toBe("folder")
  expect(result.catalog.modalities.dna.categories[result.target.entry].parent_key).toBe("empty")
  expect(draft.modalities.dna.categories.empty.node_kind).toBe("entry")
  expect(result.catalog.modalities.dna.categories.mpn).toEqual(draft.modalities.dna.categories.mpn)
})
