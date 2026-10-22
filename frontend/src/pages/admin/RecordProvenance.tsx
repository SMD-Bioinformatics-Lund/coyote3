import { ShieldCheck } from "lucide-react"
import { TableBadge } from "@/components/ui/table-badge"
import { provenanceLabel, type RecordProvenanceData } from "./record-provenance"

export function RecordProvenance({ record }: { record: RecordProvenanceData }) {
  if (record.system_managed || record.system_installed) {
    return <TableBadge className="gap-1 border-primary/25 bg-primary/10 text-primary" title="Supplied with Coyote3. Available actions follow the resource protection policy.">
      <ShieldCheck className="h-4 w-4 text-primary" role="img" aria-label="System installed" />
      System
    </TableBadge>
  }
  return <span className="break-words">{provenanceLabel(record)}</span>
}
