import type { FactDefinition, OutputNode } from "./clinical-rules-types"

export function factOutput(fact: FactDefinition): OutputNode {
  const base = { path: fact.path, missing: "error" as const }
  if (fact.kind === "string_list") return { ...base, type: "list", formatter: "text", conjunction: "and" }
  if (["number", "integer"].includes(fact.kind)) return { ...base, type: "number", precision: fact.kind === "integer" ? 0 : 2, unit: fact.unit === "%" ? "%" : "" }
  return { ...base, type: "fact", formatter: "text" }
}

export function sentenceTemplate(nodes: OutputNode[]) {
  const tokens = new Map<string, OutputNode>()
  const text = nodes.map(node => {
    if (node.type === "text") return node.value
    if (node.type === "paragraph_break") return "\n\n"
    const base = "path" in node ? node.path : node.type === "renderer" ? `renderer:${node.name}` : `plural:${node.count_path}`
    let key = base
    let count = 1
    while (tokens.has(key)) key = `${base}#${++count}`
    tokens.set(key, node)
    return `{{${key}}}`
  }).join("")
  return { text, tokens }
}

export function parseSentence(text: string, tokens: Map<string, OutputNode>, facts: FactDefinition[]): OutputNode[] {
  const nodes: OutputNode[] = []
  let end = 0
  for (const match of text.matchAll(/\{\{([^{}]+)\}\}/g)) {
    const before = text.slice(end, match.index)
    if (before.includes("{{") || before.includes("}}")) throw new Error("Complete each placeholder with {{ and }}.")
    if (before) nodes.push({ type: "text", value: before })
    const key = match[1].trim()
    const fact = facts.find(item => item.path === key && item.kind !== "object_list")
    const node = tokens.get(key) || (fact ? factOutput(fact) : undefined)
    if (!node) throw new Error(`Unknown placeholder: ${key}. Use Insert value to choose an available value.`)
    nodes.push({ ...node })
    end = match.index! + match[0].length
  }
  const after = text.slice(end)
  if (after.includes("{{") || after.includes("}}")) throw new Error("Complete each placeholder with {{ and }}.")
  if (after || !nodes.length) nodes.push({ type: "text", value: after })
  return nodes
}
