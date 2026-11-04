import type { CatalogNavigationNode, Discovery, Offering } from "./offering-types"
import { inheritCatalogInformation } from "./catalog-information"

export type CatalogNavigationOffering = Pick<Offering, "offering_id" | "modality" | "family"
  | "group_id" | "group_label" | "diagnosis_id" | "diagnosis_label">

export type CatalogBrowseNode<T extends CatalogNavigationOffering = Offering> = CatalogNavigationNode & {
  level: "modality" | "family" | "group" | "diagnosis"
  offerings: T[]
  source_node_id?: string
}

const families: Record<string, { label: string; names: string[] }> = {
  wgs: { label: "WGS", names: ["whole genome sequencing", "whole genome sequencing (wgs)"] },
  wts: { label: "WTS", names: ["whole transcriptome sequencing", "whole transcriptome sequencing (wts)"] },
  "panel-dna": { label: "Panels", names: ["targeted dna panel", "panel dna"] },
  "panel-rna": { label: "Panels", names: ["targeted rna panel", "panel rna"] },
  wes: { label: "WES", names: ["whole exome sequencing", "whole exome sequencing (wes)"] },
}

/** Group reviewed offerings by exact modality, method, group and diagnosis identities. */
export function catalogNavigation<T extends CatalogNavigationOffering = Offering>(publication?: {
  navigation: Discovery["navigation"]; offerings: T[]
}): CatalogBrowseNode<T>[] {
  if (!publication) return []
  const source = publication.navigation || []
  const sourceById = new Map(source.map(node => [node.node_id, node]))
  const descendants = (node: CatalogNavigationNode) => source.filter(candidate => {
    const seen = new Set<string>()
    let current: CatalogNavigationNode | undefined = candidate
    while (current && !seen.has(current.node_id)) {
      if (current.node_id === node.node_id) return true
      seen.add(current.node_id)
      current = sourceById.get(current.parent_id || "")
    }
    return false
  }).flatMap(child => child.offering_id ? [child.offering_id] : [])
  const nodes: CatalogBrowseNode<T>[] = []
  const add = (path: string[], label: string, level: CatalogBrowseNode["level"],
    offerings: T[], names: string[] = []) => {
    const ids = new Set(offerings.map(item => item.offering_id))
    const labels = new Set([label, path.at(-1) || "", ...names].map(value => value.toLocaleLowerCase()))
    // Only a named ancestor may supply parent wording. A service is never used as
    // a substitute for its group, even if it is the group's only published test.
    const information = source.find(node => !node.offering_id
      && [node.label, node.title].some(value => labels.has(value.toLocaleLowerCase()))
      && descendants(node).length > 0 && descendants(node).every(id => ids.has(id)))
    nodes.push({
      description: "", subheading: "", input_material: [], sample_modes: [],
      analysis: [], turnaround: "", report_deliverables: [], clinical_indications: [],
      limitations: "", public_notes: "", methodology: "", ordering_information: "",
      ...information,
      // The public tree follows service identities rather than authoring placement.
      node_id: JSON.stringify(path), parent_id: path.length > 1 ? JSON.stringify(path.slice(0, -1)) : null,
      label, title: information?.title || label,
      source_node_id: information?.node_id,
      offering_id: level === "diagnosis" && offerings.length === 1 ? offerings[0].offering_id : null,
      level, offerings,
    })
  }
  for (const modality of ["dna", "rna"] as const) {
    const scoped = publication.offerings.filter(item => item.modality === modality)
    if (!scoped.length) continue
    add([modality], modality.toUpperCase(), "modality", scoped)
    const methods = [...new Set(scoped.map(item => item.family))].sort((a, b) => {
      const order = modality === "dna" ? ["wgs", "panel-dna"] : ["wts", "panel-rna"]
      return (order.includes(a) ? order.indexOf(a) : order.length)
        - (order.includes(b) ? order.indexOf(b) : order.length) || a.localeCompare(b)
    })
    for (const method of methods) {
      const family = scoped.filter(item => item.family === method)
      add([modality, method], families[method]?.label || method, "family", family, families[method]?.names)
      const groups = [...new Map(family.map(item => [item.group_id, item.group_label])).entries()]
        .sort((a, b) => a[1].localeCompare(b[1]))
      for (const [group, groupLabel] of groups) {
        const grouped = family.filter(item => item.group_id === group)
        add([modality, method, group], groupLabel, "group", grouped)
        const diagnoses = [...new Map(grouped.map(item => [item.diagnosis_id, item.diagnosis_label])).entries()]
          .sort((a, b) => a[1].localeCompare(b[1]))
        for (const [diagnosis, diagnosisLabel] of diagnoses) {
          add([modality, method, group, diagnosis], diagnosisLabel, "diagnosis",
            grouped.filter(item => item.diagnosis_id === diagnosis))
        }
      }
    }
  }
  for (const [index, node] of nodes.entries()) {
    nodes[index] = { ...node, ...inheritCatalogInformation(node,
      nodes.find(parent => parent.node_id === node.parent_id)) }
  }
  return nodes
}
