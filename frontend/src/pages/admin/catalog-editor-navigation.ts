import { catalogNavigation, type CatalogBrowseNode, type CatalogNavigationOffering } from "../catalog/catalog-navigation"
import { emptyCatalogInformation } from "../catalog/catalog-information"
import type { CatalogNavigationNode } from "../catalog/offering-types"
import { CATALOG_INHERITED_FIELDS, effectiveCatalogEntry } from "./catalog-hierarchy"
import type { Catalog, Category, SourceOptions } from "./catalog-types"

export type CatalogEditorTarget = { section: string; entry: string }
export type CatalogEditorService = CatalogNavigationOffering & CatalogEditorTarget
export type CatalogEditorNode = CatalogBrowseNode<CatalogEditorService> & { target?: CatalogEditorTarget }

/** Add a child and make an unbound parent a grouping section; preserve existing assay bindings. */
export function addCatalogChild(catalog: Catalog, parent: CatalogEditorTarget,
  kind: "entry" | "folder"): { catalog: Catalog; target: CatalogEditorTarget } {
  const section = catalog.modalities[parent.section]
  const key = crypto.randomUUID().replaceAll("-", "_")
  const child: Category = { label: kind === "folder" ? "New subsection" : parent.entry ? "New child" : "New entry",
    node_kind: kind, parent_key: parent.entry || null, gene_lists: [] }
  const categories = { ...section.categories, [key]: child }
  if (parent.entry && !effectiveCatalogEntry(section, parent.entry).asp_id) {
    categories[parent.entry] = { ...categories[parent.entry], node_kind: "folder" }
  }
  return { catalog: { ...catalog, modalities: { ...catalog.modalities, [parent.section]: {
    ...section, categories,
  } } }, target: { section: parent.section, entry: key } }
}

/** Combine resource browse levels with individual draft entries and custom authoring sections. */
export function catalogEditorNavigation(catalog?: Catalog | null, sources?: SourceOptions): CatalogEditorNode[] {
  if (!catalog || !sources) return []
  const services: CatalogEditorService[] = []
  const navigation: CatalogNavigationNode[] = []
  const targets = new Map<string, CatalogEditorTarget>()
  for (const [section, modality] of Object.entries(catalog.modalities)) {
    const root = `section:${section}`
    targets.set(root, { section, entry: "" })
    navigation.push({ ...emptyCatalogInformation(modality.title || modality.label || section), ...modality,
      label: modality.label || section, title: modality.title || modality.label || section,
      description: modality.description || "", node_id: root, parent_id: null,
      turnaround: modality.tat || "",
    } as CatalogNavigationNode)
    for (const [entry, value] of Object.entries(modality.categories)) {
      const effective = effectiveCatalogEntry(modality, entry)
      const assay = sources.asps.find(item => item.asp_id === effective.asp_id)
      const config = sources.aspcs.find(item => item.aspc_id === (effective.aspc_id || effective.aspc_ids?.production))
      const sourceId = `entry:${section}:${entry}`
      targets.set(sourceId, { section, entry })
      const id = value.catalog_id || JSON.stringify([section, entry])
      const linked = value.node_kind !== "folder" && assay && config && config.asp_id === assay.asp_id
        && assay.family && assay.group
        && (assay.category === "dna" || assay.category === "rna")
      if (linked) {
        const diagnosis = config.diagnosis_id || effective.diagnosis_id || "base"
        services.push({ offering_id: id, section, entry, modality: assay.category as "dna" | "rna",
          family: assay.family!, group_id: assay.group!, group_label: assay.group_label || assay.group!,
          diagnosis_id: diagnosis, diagnosis_label: config.diagnosis_label
            || (diagnosis === "base" ? "No diagnosis / General testing" : diagnosis),
        })
      }
      navigation.push({ ...emptyCatalogInformation(value.title || value.label || entry), ...effective,
        label: value.label || value.title || entry, title: value.title || value.label || entry,
        description: effective.description || "", node_id: sourceId,
        parent_id: value.parent_key ? `entry:${section}:${value.parent_key}` : root,
        offering_id: linked ? id : null, turnaround: effective.tat || "",
      } as CatalogNavigationNode)
    }
  }
  const nodes: CatalogEditorNode[] = catalogNavigation({ offerings: services, navigation }).flatMap(node => {
    const sourceTarget = node.source_node_id ? targets.get(node.source_node_id) : undefined
    const sourceFolder = sourceTarget?.entry && catalog.modalities[sourceTarget.section].categories[sourceTarget.entry].node_kind === "folder"
    const result: CatalogEditorNode[] = [{ ...node,
      target: node.level === "diagnosis" && !sourceFolder ? undefined : sourceTarget,
    }]
    if (node.level === "diagnosis") {
      for (const service of node.offerings) {
        const entry = catalog.modalities[service.section].categories[service.entry]
        result.push({ ...node, node_id: JSON.stringify([node.node_id, service.offering_id]),
          parent_id: node.node_id, label: entry.title || entry.label || service.entry,
          title: entry.title || entry.label || service.entry, offerings: [service], target: service,
        })
      }
    }
    return result
  })
  const represented = new Map(nodes.flatMap(node => node.target
    ? [[node.target.entry ? `entry:${node.target.section}:${node.target.entry}` : `section:${node.target.section}`, node.node_id] as const] : []))
  const sourceById = new Map(navigation.map(node => [node.node_id, node]))
  const visiting = new Set<string>()
  const addUnlinked = (sourceId: string): string | undefined => {
    if (represented.has(sourceId)) return represented.get(sourceId)
    const source = sourceById.get(sourceId)
    if (!source || visiting.has(sourceId)) return undefined
    visiting.add(sourceId)
    const parent = source.parent_id ? addUnlinked(source.parent_id) : undefined
    const parentNode = nodes.find(node => node.node_id === parent)
    const levels = ["modality", "family", "group", "diagnosis"] as const
    const node: CatalogEditorNode = { ...source, parent_id: parent || null,
      node_id: sourceId, source_node_id: sourceId, target: targets.get(sourceId), offerings: [],
      level: parentNode ? levels[Math.min(levels.indexOf(parentNode.level) + 1, 3)] : "modality" }
    nodes.push(node)
    represented.set(sourceId, sourceId)
    visiting.delete(sourceId)
    return sourceId
  }
  for (const source of navigation) {
    if (!represented.has(source.node_id)) addUnlinked(source.node_id)
  }
  // Custom authoring sections keep their children in place after source attachment.
  for (const node of nodes) {
    if (!node.target?.entry) continue
    const parent = sourceById.get(`entry:${node.target.section}:${node.target.entry}`)?.parent_id
    if (parent && parent !== node.node_id && represented.get(parent) === parent) node.parent_id = parent
  }
  return nodes
}

/** Add missing parent folders to one source section, retaining effective existing entry values. */
export function addCatalogParentDefaults(catalog: Catalog, node: CatalogEditorNode,
  nodes: CatalogEditorNode[]): { catalog: Catalog; target: CatalogEditorTarget } {
  const sections = new Set(node.offerings.map(item => item.section))
  if (sections.size !== 1) throw new Error("Select a source section before adding shared defaults.")
  const section = [...sections][0]
  const modality = catalog.modalities[section]
  const categories = { ...modality.categories }
  const path: CatalogEditorNode[] = []
  let current: CatalogEditorNode | undefined = node
  while (current && current.level !== "modality") {
    path.unshift(current)
    current = nodes.find(parent => parent.node_id === current?.parent_id)
  }
  let parentKey: string | null = null
  for (const part of path) {
    if (part.target?.section === section) { parentKey = part.target.entry || null; continue }
    const key = `folder_${crypto.randomUUID().replaceAll("-", "_")}`
    categories[key] = { node_kind: "folder", label: part.label, title: part.label, parent_key: parentKey }
    parentKey = key
  }
  if (!parentKey) throw new Error("Edit the section defaults at this level.")
  const parent = effectiveCatalogEntry({ ...modality, categories }, parentKey)
  const empty = (value: unknown) => value == null || value === ""
    || Array.isArray(value) && !value.length
    || typeof value === "object" && !Object.keys(value).length
  for (const service of node.offerings) {
    const existing = categories[service.entry]
    if (existing.parent_key === parentKey) continue
    const effective = effectiveCatalogEntry(modality, service.entry)
    const fields = CATALOG_INHERITED_FIELDS.filter(field =>
      !existing.clear_fields?.includes(field)
      && empty(existing[field])
      && JSON.stringify(effective[field]) !== JSON.stringify(parent[field]))
    const preserved = Object.fromEntries(fields.map(field => [field, effective[field]])) as Partial<Category>
    const suppressed = fields.filter(field => empty(effective[field]) && !empty(parent[field]))
    categories[service.entry] = { ...existing, ...preserved, parent_key: parentKey,
      ...(suppressed.length ? { clear_fields: [...new Set([...(existing.clear_fields || []), ...suppressed])] } : {}),
    }
  }
  return { catalog: { ...catalog, modalities: { ...catalog.modalities,
    [section]: { ...modality, categories } } }, target: { section, entry: parentKey } }
}
