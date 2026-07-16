import { ShieldCheck } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { uiRouteRegistry, type UiRouteAudit } from "@/lib/routes/ui-route-registry"
import type { ColumnDef } from "@tanstack/react-table"

const areaTone: Record<UiRouteAudit["area"], string> = {
  clinical: "border-dna/30 bg-dna/10 text-dna",
  public: "border-panel/30 bg-panel/10 text-panel",
  admin: "border-warn/30 bg-warn/10 text-warn",
  account: "border-primary/30 bg-primary/10 text-primary",
  system: "border-muted-foreground/30 bg-muted text-muted-foreground",
}

const columns: ColumnDef<UiRouteAudit, any>[] = [
  {
    accessorKey: "path",
    header: "Route",
    cell: ({ row }) => <span className="font-mono text-[11px] font-bold text-primary">{row.original.path}</span>,
  },
  {
    accessorKey: "page",
    header: "Page",
    cell: ({ row }) => <span className="font-bold">{row.original.page}</span>,
  },
  {
    accessorKey: "area",
    header: "Area",
    cell: ({ row }) => (
      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-black uppercase ${areaTone[row.original.area]}`}>
        {row.original.area}
      </span>
    ),
  },
  {
    id: "api",
    header: "API Dependencies",
    accessorFn: (row) => row.api.join(" "),
    cell: ({ row }) => (
      <div className="flex max-w-[460px] flex-wrap gap-1">
        {row.original.api.length ? (
          row.original.api.map((item) => (
            <Badge key={item} variant="outline" className="max-w-full truncate font-mono text-[10px]">
              {item}
            </Badge>
          ))
        ) : (
          <span className="text-muted-foreground">No remote data</span>
        )}
      </div>
    ),
  },
  {
    id: "dataUsed",
    header: "UI Data Usage",
    accessorFn: (row) => row.dataUsed.join(" "),
    cell: ({ row }) => (
      <div className="max-w-[520px] text-xs leading-5 text-muted-foreground">
        {row.original.dataUsed.join(", ")}
      </div>
    ),
  },
]

export function UiRouteAuditPage() {
  const apiBacked = uiRouteRegistry.filter((route) => route.api.length).length
  return (
    <PageShell
      eyebrow="Admin"
      title="UI Route & Data Audit"
      description="Inventory of client routes, backing API calls, and the data each view consumes. Use this as the checklist for route-by-route live verification."
      actions={
        <div className="inline-flex items-center gap-2 rounded-xl border border-border bg-background/80 px-3 py-2 text-sm font-bold shadow-sm">
          <ShieldCheck className="h-4 w-4 text-primary" />
          {apiBacked}/{uiRouteRegistry.length} API-backed
        </div>
      }
    >
      <section className="surface-panel p-3">
        <DataTable
          columns={columns}
          data={uiRouteRegistry}
          filename="coyote3-ui-route-audit.csv"
        />
      </section>
    </PageShell>
  )
}
