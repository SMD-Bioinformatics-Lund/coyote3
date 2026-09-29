import { ShieldCheck } from "lucide-react"
import { provenanceLabel, type RecordProvenanceData } from "./record-provenance"

export function RecordProvenance({ record }: { record: RecordProvenanceData }) {
  return <span className="inline-flex max-w-full items-center gap-1 break-words" title={record.system_managed ? "System-managed record" : undefined}>
    {record.system_managed && <ShieldCheck className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />}
    <span className="min-w-0 break-words">{provenanceLabel(record)}</span>
  </span>
}
