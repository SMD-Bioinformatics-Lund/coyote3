export type RecordProvenanceData = {
  system_managed?: boolean
  created_by?: string | null
}

export function provenanceLabel(record: RecordProvenanceData) {
  return record.system_managed ? "System" : record.created_by?.trim() || "Unknown"
}
