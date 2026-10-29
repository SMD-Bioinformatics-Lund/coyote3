/** Application-owned fields at configuration-record boundaries, never inside rule content. */
const metadataFields = new Set([
  "_id", "id_", "created_by", "updated_by", "created_at", "updated_at", "created_on", "updated_on",
  "version", "content_version", "revision", "content_hash", "status", "active", "review", "lifecycle",
  "provenance", "content_editors", "system_installed", "system_managed", "version_history",
  "published_at", "published_on", "published_by", "retired_at", "retired_on", "retired_by",
  "retired_reason", "approved_at", "approved_by", "submitted_at", "submitted_by", "effective_from",
  "supersedes_id", "installed_by", "installed_on", "review_dependencies", "review_reason",
  "base_version", "is_current", "query_id", "scope_key", "rule_set_id", "catalog_key", "change_summary",
])

const recordChildren = ["panel", "gene_lists", "configurations"] as const

/** Remove audit metadata from records and setup children while preserving arbitrary clinical content. */
export function configurationContent(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(configurationContent)
  if (!value || typeof value !== "object") return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => !metadataFields.has(key))
    .map(([key, nested]) => [key, recordChildren.includes(key as typeof recordChildren[number])
      ? configurationContent(nested) : nested]))
}

/** Attach only recognized audit fields to the same ordered portable records; never copy credentials. */
export function configurationWithMetadata(content: unknown, source: unknown): unknown {
  if (Array.isArray(content)) {
    return content.map((item, index) => configurationWithMetadata(item, Array.isArray(source) ? source[index] : undefined))
  }
  if (!content || typeof content !== "object") return content
  const record = source && typeof source === "object" && !Array.isArray(source)
    ? source as Record<string, unknown> : {}
  return {
    ...Object.fromEntries(Object.entries(record).filter(([key]) => metadataFields.has(key))),
    ...Object.fromEntries(Object.entries(content).map(([key, nested]) => [key,
      recordChildren.includes(key as typeof recordChildren[number])
        ? configurationWithMetadata(nested, record[key]) : nested])),
  }
}
