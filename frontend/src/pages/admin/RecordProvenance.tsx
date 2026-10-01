import { ShieldCheck } from "lucide-react"
import { provenanceLabel, type RecordProvenanceData } from "./record-provenance"

export function RecordProvenance({ record }: { record: RecordProvenanceData }) {
  if (record.system_managed) {
    return <span title="Installed and managed by Coyote3. Available actions follow the resource protection policy.">
      <ShieldCheck className="h-4 w-4 text-primary" role="img" aria-label="System installed" />
    </span>
  }
  return <span className="break-words">{provenanceLabel(record)}</span>
}
