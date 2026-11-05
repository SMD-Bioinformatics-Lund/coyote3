export type RecordProvenanceData = {
  system_managed?: boolean
  system_installed?: boolean
  created_by?: string | null
  updated_by?: string | null
  created_on?: unknown
  created_at?: unknown
  updated_on?: unknown
  updated_at?: unknown
}

export function provenanceLabel(record: RecordProvenanceData) {
  return record.system_managed || record.system_installed ? "System" : record.created_by?.trim() || "Unknown"
}

/** Search only the author label and timestamp displayed in a provenance cell. */
export function provenanceSearchValue(record: RecordProvenanceData, kind: "created" | "updated" = "created") {
  return kind === "created"
    ? [provenanceLabel(record), record.created_on ?? record.created_at]
    : [record.updated_by?.trim() || "Unknown", record.updated_on ?? record.updated_at]
}
