import { ShieldCheck } from "lucide-react"
import { TableBadge } from "@/components/ui/table-badge"
import { TimeDisplay } from "@/components/ui/time-display"
import { provenanceLabel, type RecordProvenanceData } from "./record-provenance"

export function RecordProvenance({ record, kind = "created" }: { record: RecordProvenanceData; kind?: "created" | "updated" }) {
  const timestamp = kind === "created" ? record.created_on ?? record.created_at : record.updated_on ?? record.updated_at
  return <div className="flex flex-col items-start gap-0.5">
    {kind === "created" && (record.system_managed || record.system_installed) ? <TableBadge className="gap-1 border-primary/25 bg-primary/10 text-primary" title="Installed by Coyote3. This record is read-only; create a separate resource to customize it.">
      <ShieldCheck className="h-4 w-4 text-primary" role="img" aria-label="System installed" />
      System
    </TableBadge> : <span className="break-words">{kind === "created" ? provenanceLabel(record) : record.updated_by?.trim() || "Unknown"}</span>}
    {timestamp != null && timestamp !== "" && <TimeDisplay value={timestamp} className="type-meta font-normal text-muted-foreground" />}
  </div>
}
