import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { AlertTriangle, ExternalLink } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { BulkActionDropdown, BulkActionOption } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import {
  StatusBadges,
  TierBadge,
} from "@/lib/variant-ui"
import {
  findingRowClass,
  fusionCallers,
  fusionGenes,
  selectedFusionCall,
  statusLabels,
  tierValue,
} from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"

const fusionBulkActions: BulkActionOption[] = [
  { value: "fp", label: "Mark False Positive" },
  { value: "unfp", label: "Unmark False Positive" },
  { value: "irrelevant", label: "Mark Irrelevant" },
  { value: "relevant", label: "Unmark Irrelevant" },
]

export function FusionsTab({ sampleId }: { sampleId: string }) {
  const bulkAction = useBulkFindingAction(sampleId, "fusion")
  const location = useLocation()
  const {
    page,
    perPage,
    sortParam,
    debouncedSearchText,
    tableProps,
  } = useClinicalTableState({ prefix: "fusion", tab: "fusions" })
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-fusions", sampleId, page, perPage, debouncedSearchText, sortParam],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      })
      if (debouncedSearchText) params.set("q", debouncedSearchText)
      if (sortParam) params.set("sort", sortParam)
      return api.get(`/samples/${sampleId}/fusions?${params.toString()}`).then(res => res.data)
    },
    placeholderData: (previousData) => previousData,
    staleTime: CLINICAL_TABLE_STALE_MS,
    gcTime: CLINICAL_TABLE_CACHE_MS,
  })

  if (isLoading) return <AppLoader label="Loading fusions" />
  if (error) return <div className="text-destructive p-4 flex gap-2"><AlertTriangle /> Error loading Fusions</div>

  const fusions = data?.fusions || []
  const fusionCount = Number(data?.meta?.count ?? fusions.length)
  const hasNext = Boolean(data?.meta?.has_next)
  const hasPrevious = Boolean(data?.meta?.has_previous)

  const columns: ColumnDef<any, any>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate" as any)}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
          className="table-checkbox"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          className="table-checkbox"
        />
      ),
      enableSorting: false,
    },
    {
      id: "badges",
      header: "Status",
      accessorFn: (row) => statusLabels(row),
      meta: { exportValue: statusLabels },
      cell: ({ row }) => <StatusBadges finding={row.original} />,
    },
    {
      id: "gene1",
      header: "Gene 1",
      accessorFn: (row) => fusionGenes(row)[0] || "-",
      cell: ({ row }) => {
        const genes = fusionGenes(row.original)
        return <span className="font-bold text-primary hover:underline cursor-pointer">{genes[0] || "-"}</span>
      }
    },
    {
      id: "gene2",
      header: "Gene 2",
      accessorFn: (row) => fusionGenes(row)[1] || "-",
      cell: ({ row }) => {
        const genes = fusionGenes(row.original)
        return <span className="font-bold text-primary hover:underline cursor-pointer">{genes[1] || "-"}</span>
      }
    },
    {
      id: "effect",
      header: "Effect",
      accessorFn: (row) => selectedFusionCall(row)?.effect || row.frame || "Unknown",
      cell: ({ row }) => {
        const f = selectedFusionCall(row.original)?.effect || row.original.frame
        return (
          <span className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${f === 'in-frame' ? 'bg-pass/10 text-pass' : 'bg-muted text-muted-foreground'}`}>
            {f || "Unknown"}
          </span>
        )
      }
    },
    {
      id: "spanpairs",
      header: "Spanning pairs",
      accessorFn: (row) => selectedFusionCall(row)?.spanpairs || row.supporting_reads?.span || 0,
      cell: ({ row }) => <span className="font-mono text-xs">{selectedFusionCall(row.original)?.spanpairs || row.original.supporting_reads?.span || "-"}</span>
    },
    {
      id: "unique_spanpairs",
      header: "Unique spanning reads",
      accessorFn: (row) => selectedFusionCall(row)?.spanreads || row.supporting_reads?.split || 0,
      cell: ({ row }) => <span className="font-mono text-xs">{selectedFusionCall(row.original)?.spanreads || row.original.supporting_reads?.split || "-"}</span>
    },
    {
      id: "fusion_points",
      header: "Fusion points",
      accessorFn: (row) => {
        const call = selectedFusionCall(row)
        return [call?.breakpoint1, call?.breakpoint2].filter(Boolean).join(", ") || row.breakpoints?.join(", ") || "-"
      },
      cell: ({ row }) => {
        const call = selectedFusionCall(row.original)
        const bps = [call?.breakpoint1, call?.breakpoint2].filter(Boolean)
        const breakpoints = bps.length ? bps : row.original.breakpoints || []
        return (
          <div className="flex flex-col gap-0.5 text-[11px] leading-tight">
            {breakpoints.map((bp: string, i: number) => (
              <span key={i} className="font-mono bg-muted/50 px-1.5 py-0.5 rounded w-max">{bp}</span>
            ))}
          </div>
        )
      }
    },
    {
      id: "tier",
      accessorFn: tierValue,
      meta: { exportValue: (row: any) => tierValue(row) === 999 ? "" : tierValue(row), headerClassName: "w-14 min-w-14", cellClassName: "w-14 min-w-14" },
      header: "Tier",
      cell: ({ row }) => <TierBadge tier={tierValue(row.original)} />,
    },
    {
      id: "description",
      header: "Description",
      accessorFn: (row) => selectedFusionCall(row)?.desc || row.desc || "-",
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{selectedFusionCall(row.original)?.desc || row.original.desc || "-"}</span>
    },
    {
      id: "callers",
      header: "Callers",
      accessorFn: fusionCallers,
      cell: ({ row }) => <span className="text-xs uppercase font-medium text-muted-foreground">{fusionCallers(row.original)}</span>
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        return (
          <div className="flex items-center gap-1">
            <VariantActionButtons sampleId={sampleId} resourceType="fusion" variant={row.original} compact />
            <Link
              to={`/samples/${sampleId}/fusion/${row.original._id}`}
              state={{ from: `${location.pathname}${location.search}` }}
              className="inline-block rounded-md bg-primary/10 p-0.5 text-primary shadow-sm transition-colors duration-100 hover:bg-primary hover:text-white"
            >
              <span title="View Detail"><ExternalLink className="w-4 h-4" /></span>
            </Link>
          </div>
        )
      }
    }
  ]

  return (
    <div className="glass-card flex flex-col overflow-hidden p-2">
      <DataTable
        columns={columns}
        data={fusions}
        rowLabel="fusions"
        totalCount={fusionCount}
        page={Number(data?.meta?.page ?? page)}
        perPage={Number(data?.meta?.per_page ?? perPage)}
        hasNext={hasNext}
        hasPrevious={hasPrevious}
        {...tableProps}
        filename={`fusions_${sampleId}.csv`}
        getRowClassName={findingRowClass}
        renderToolbar={(table) => (
          <BulkActionDropdown
            selectedCount={Object.keys(table.getState().rowSelection).length}
            actions={fusionBulkActions}
            isPending={bulkAction.isPending}
            onAction={(action) => bulkAction.mutateAsync({
              action,
              resourceIds: table.getSelectedRowModel().rows.map((row: any) => String(row.original._id)),
            })}
          />
        )}
        renderExportButton={() => (
          <ServerCsvButton
            endpoint={`/samples/${sampleId}/fusions/exports/context`}
            fallbackFilename={`${sampleId}.filtered.fusions.csv`}
            label="Export to CSV"
          />
        )}
      />
    </div>
  )
}
