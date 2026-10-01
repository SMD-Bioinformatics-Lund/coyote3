import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ColumnDef } from "@tanstack/react-table"
import { ArrowLeft, Trash2 } from "lucide-react"
import { useMemo } from "react"
import { Link, useParams } from "react-router-dom"
import { ErrorBox, Loading } from "./resource-presentation"
import { columnsFor } from "./resource-values"

export function CoverageBlacklistPage() {
  const { group = "" } = useParams()
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["coverage-blacklisted", group],
    queryFn: () => api.get(`/coverage/blacklisted/${group}`).then((res) => res.data),
    enabled: Boolean(group),
  })
  const removeEntry = useMutation({
    mutationFn: (id: string) => api.delete(`/coverage/blacklist/entries/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["coverage-blacklisted", group] })
      notifySuccess("Blacklist entry removed", "The coverage blacklist entry was deleted.", "Coverage")
    },
    onError: (error) => {
      notifyActionError("Unable to remove blacklist entry", error, "Coverage")
    },
  })

  const rows = useMemo(() => {
    const blacklisted = data?.blacklisted || {}
    return Object.entries(blacklisted).flatMap(([gene, info]: [string, any]) => {
      const regions = info?.regions || info?.entries || []
      if (Array.isArray(regions) && regions.length) {
        return regions.map((entry: any) => ({ gene, ...entry, id: entry._id || entry.id || entry.coord || gene }))
      }
      return [{ gene, ...(typeof info === "object" ? info : {}), id: info?._id || info?.id || gene }]
    })
  }, [data])

  const columns: ColumnDef<any, any>[] = [
    ...columnsFor(rows, ["gene", "region", "coord", "smp_grp", "_id"]).slice(0, 8),
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const id = String(row.original._id || row.original.id || row.original.gene)
        return (
          <button
            onClick={() => removeEntry.mutate(id)}
            disabled={removeEntry.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-destructive/30 px-2 py-1 text-xs font-bold text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove
          </button>
        )
      },
    },
  ]

  return (
    <PageShell
      eyebrow="Coverage"
      title={`Blacklisted Regions: ${group}`}
      actions={<Link to="/samples" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"><ArrowLeft className="h-4 w-4" /> Samples</Link>}
    >
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <section className="surface-panel p-3">
          <DataTable columns={columns} data={rows} filename={`coverage_blacklist_${group}.csv`} />
        </section>
      )}
    </PageShell>
  )
}
