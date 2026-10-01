import type {
  FactDefinition,
  OutputNode
} from "./clinical-rules-types"


export function outputPreview(nodes: OutputNode[], facts: FactDefinition[]) {
  return nodes.map((node) => {
    if (node.type === "text") return node.value
    if (node.type === "paragraph_break") return "\n\n"
    if (node.type === "renderer") return `[${node.name.replaceAll("_", " ")}]`
    const path = "count_path" in node ? node.count_path : "path" in node ? node.path : ""
    return `[${facts.find((fact) => fact.path === path)?.label || path}]`
  }).join("")
}
