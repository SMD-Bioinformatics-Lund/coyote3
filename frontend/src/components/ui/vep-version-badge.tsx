import { TableBadge } from "@/components/ui/table-badge"

export function VepVersionBadge({ version }: { version: unknown }) {
  const value = String(version ?? "").trim().replace(/^[vV]+/, "").replace(/(?:\.0)+$/, "")
  if (!value) return null
  return <TableBadge className="badge-info" title={`Sample VEP version; metadata is requested using vep_id ${value}`}>
    VEP {value}
  </TableBadge>
}
