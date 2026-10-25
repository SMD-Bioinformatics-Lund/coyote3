import { parseDocument } from "yaml"

export const BULK_LIMIT = 100
export const BULK_BYTES = 1024 * 1024
export type BulkRecord = Record<string, unknown>
export type BulkKind = "diagnoses" | "assay-groups" | "asp" | "aspc" | "genelists"

export const bulkDefinitions = {
  diagnoses: {
    permission: "assay.panel:edit", identity: "diagnosis_id",
    example: { diagnosis_id: "example-diagnosis", display_name: "Example diagnosis", description: "Replace with your diagnosis description", is_active: true, asp_ids: [] },
    required: ["diagnosis_id", "display_name"],
  },
  "assay-groups": {
    permission: "assay.panel:edit", identity: "group_id",
    example: { group_id: "example-group", display_name: "Example group", description: "Replace with your clinical group description", parent_group_id: null },
    required: ["group_id", "display_name"],
  },
  asp: { permission: "assay.panel:create", identity: "asp_id" },
  aspc: { permission: "assay.config:create", identity: "asp_id,diagnosis_id,environment" },
  genelists: { permission: "gene_list.insilico:create", identity: "isgl_id" },
} as const

/** Read a bounded list without YAML aliases, custom tags or silently discarded keys. */
export function parseBulkFile(text: string, filename: string, keys: string[], required: string[], identity: string): BulkRecord[] {
  if (new TextEncoder().encode(text).length > BULK_BYTES) throw new Error("File must be no larger than 1 MiB")
  if (!/\.(json|ya?ml)$/i.test(filename)) throw new Error("Choose a JSON or YAML file")
  let value: unknown
  if (/\.json$/i.test(filename)) value = JSON.parse(text)
  else {
    const document = parseDocument(text, { schema: "core", uniqueKeys: true })
    const problem = document.errors[0] ?? document.warnings[0]
    if (problem) throw new Error(`Invalid YAML: ${problem.message}`)
    value = document.toJS({ maxAliasCount: 0 })
  }
  if (!Array.isArray(value) || !value.length || value.length > BULK_LIMIT) throw new Error(`Provide a list of 1–${BULK_LIMIT} records`)
  const seen = new Set<string>()
  return value.map((record: unknown, index) => {
    if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error(`Row ${index + 1}: expected an object`)
    const item = record as BulkRecord
    const unknown = Object.keys(item).filter((key) => !keys.includes(key))
    if (unknown.length) throw new Error(`Row ${index + 1}: unsupported keys: ${unknown.join(", ")}`)
    const missing = required.filter((key) => item[key] == null || item[key] === "")
    if (missing.length) throw new Error(`Row ${index + 1}: missing required keys: ${missing.join(", ")}`)
    const parts = identity.split(",").map((key) => item[key])
    if (parts.some((id) => typeof id !== "string" || !id.trim())) throw new Error(`Row ${index + 1}: ${identity} must contain nonempty strings`)
    const id = parts.join(" / ")
    const canonical = JSON.stringify(parts.map((id) => String(id).trim().toLowerCase()))
    if (seen.has(canonical)) throw new Error(`Row ${index + 1}: duplicate ${identity}: ${id}`)
    seen.add(canonical)
    return item
  })
}
