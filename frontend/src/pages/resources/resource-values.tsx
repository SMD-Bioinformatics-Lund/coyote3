import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import { localDate } from "@/lib/detail-formatters"
import { ColumnDef } from "@tanstack/react-table"


export function columnsFor(rows: any[], preferred: string[] = []): ColumnDef<any, any>[] {
  const keys = [...preferred, ...rows.flatMap((row) => Object.keys(row || {}))]
  const seen = new Set<string>()
  return keys
    .filter((key) => {
      if (seen.has(key) || key.startsWith("_rev") || key === "knowledgebase_markers") return false
      seen.add(key)
      return rows.some((row) => row?.[key] !== undefined)
    })
    .slice(0, 12)
    .map((key) => ({
      id: key,
      header: key.replaceAll("_", " "),
      accessorFn: (row: any) => {
        const value = row?.[key]
        if (Array.isArray(value)) return value.join(", ")
        if (value && typeof value === "object") return JSON.stringify(value)
        return value ?? ""
      },
      cell: ({ row }) => {
        const value = row.original?.[key]
        const label = Array.isArray(value) ? value.join(", ") : value && typeof value === "object" ? JSON.stringify(value) : String(value ?? "-")
        if (["hgnc_symbol", "symbol", "gene"].includes(key)) {
          return (
            <GeneWithOncoKbBadge
              gene={label}
              displayGene={label}
              hgncId={row.original?.hgnc_id || row.original?._id}
              showOncoKbBadge={false}
              markers={row.original?.knowledgebase_markers}
            />
          )
        }
        return <span className="block max-w-[24rem] truncate text-xs" title={label}>{label}</span>
      },
    }))
}

export function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean)
  if (value === undefined || value === null || value === "") return []
  return String(value).split(/[;,]/).map((item) => item.trim()).filter(Boolean)
}

export function display(value: unknown) {
  if (value === undefined || value === null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "-"
  return String(value)
}

export function formatDate(value: unknown) {
  return localDate(value)
}

export function formatCoordinate(value: unknown) {
  if (typeof value === "number") return value.toLocaleString()
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toLocaleString() : display(value)
}

export function stripHtml(value: unknown) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim()
}
