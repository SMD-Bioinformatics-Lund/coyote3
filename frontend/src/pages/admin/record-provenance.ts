export type RecordProvenanceData = {
  system_managed?: boolean
  system_installed?: boolean
  created_by?: string | null
}

export function provenanceLabel(record: RecordProvenanceData) {
  return record.system_managed || record.system_installed ? "System" : record.created_by?.trim() || "Unknown"
}
