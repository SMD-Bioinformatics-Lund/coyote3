import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link } from "react-router-dom"
import { api } from "@/lib/api"
import { Activity, AlertTriangle, ExternalLink } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { BulkActionDropdown, BulkActionOption } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { ColumnDef } from "@tanstack/react-table"
import { ExpandableText } from "@/components/detail/ExpandableText"
import {
  StatusBadges,
  TierBadge,
} from "@/lib/variant-ui"
import {
  findingRowClass,
  selectedTranslocationAnnotation,
  statusLabels,
  tierValue,
  translocationGenes,
  translocationHgvs,
  translocationPanelStatus,
  translocationPositionLabel,
  translocationType,
} from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"

const translocationBulkActions: BulkActionOption[] = [
  { value: "tier_1", label: "Classify as Tier 1" },
  { value: "tier_2", label: "Classify as Tier 2" },
  { value: "tier_3", label: "Classify as Tier 3" },
  { value: "tier_4", label: "Classify as Tier 4" },
  { value: "remove_tier_1", label: "Remove Tier 1" },
  { value: "remove_tier_2", label: "Remove Tier 2" },
  { value: "remove_tier_3", label: "Remove Tier 3" },
  { value: "remove_tier_4", label: "Remove Tier 4" },
  { value: "fp", label: "Mark False Positive" },
  { value: "unfp", label: "Unmark False Positive" },
  { value: "interesting", label: "Mark Interesting" },
  { value: "uninteresting", label: "Unmark Interesting" },
]

export function TranslocationsTab({ sampleId }: { sampleId: string }) {
  const bulkAction = useBulkFindingAction(sampleId, "translocation")
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(50)
  const { data, isLoading, error } = useQuery({
    queryKey: ['sample-translocations', sampleId, page, perPage],
    queryFn: () => api.get(`/samples/${sampleId}/translocations?page=${page}&per_page=${perPage}`).then(res => res.data),
    placeholderData: (previousData) => previousData,
  })

  if (isLoading) return <div className="flex justify-center p-8"><Activity className="animate-spin text-muted-foreground" /></div>
  if (error) return <div className="text-destructive p-4 flex gap-2"><AlertTriangle /> Error loading Translocations</div>

  const translocations = data?.display_sections_data?.translocs || data?.translocations || []
  const translocationCount = Number(data?.meta?.count ?? translocations.length)
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
      accessorFn: (row) => translocationGenes(row)[0] || "-",
      cell: ({ row }) => <span className="font-bold text-primary hover:underline cursor-pointer">{translocationGenes(row.original)[0] || "-"}</span>
    },
    {
      id: "gene2",
      header: "Gene 2",
      accessorFn: (row) => translocationGenes(row)[1] || "-",
      cell: ({ row }) => <span className="font-bold text-primary hover:underline cursor-pointer">{translocationGenes(row.original)[1] || "-"}</span>
    },
    {
      id: "positions",
      header: "Positions",
      accessorFn: translocationPositionLabel,
      cell: ({ row }) => {
        const position = translocationPositionLabel(row.original)
        return (
          <span className="font-mono text-xs text-muted-foreground">
            {position}
          </span>
        )
      }
    },
    {
      id: "type",
      header: "Type",
      accessorFn: translocationType,
      cell: ({ row }) => <span className="font-semibold text-foreground text-xs">{translocationType(row.original)}</span>
    },
    {
      id: "hgvs",
      header: "HGVS",
      accessorFn: (row) => {
        const ann = selectedTranslocationAnnotation(row)
        const hgvs = translocationHgvs(ann)
        return [hgvs.coding, hgvs.protein].filter(Boolean).join(" ")
      },
      cell: ({ row }) => {
        const ann = selectedTranslocationAnnotation(row.original)
        const hgvs = translocationHgvs(ann)
        return (
          <div className="flex w-48 flex-col gap-1.5">
            <ExpandableText text={hgvs.coding || "-"} maxLength={18} className="text-xs font-mono text-muted-foreground" />
            <ExpandableText text={hgvs.protein || "-"} maxLength={18} className="text-xs font-mono font-semibold" />
          </div>
        )
      }
    },
    {
      id: "panel",
      header: "Panel",
      accessorFn: translocationPanelStatus,
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{translocationPanelStatus(row.original)}</span>
    },
    {
      id: "tier",
      header: "Tier",
      accessorFn: tierValue,
      meta: { exportValue: (row: any) => tierValue(row) === 999 ? "" : tierValue(row) },
      cell: ({ row }) => <TierBadge tier={tierValue(row.original)} />,
    },

    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        return (
          <div className="flex items-center gap-1">
            <VariantActionButtons sampleId={sampleId} resourceType="translocation" variant={row.original} compact />
            <Link to={`/samples/${sampleId}/translocation/${row.original._id}`} className="inline-block p-1.5 bg-primary/10 text-primary hover:bg-primary hover:text-white rounded-md transition-colors duration-100 shadow-sm">
              <span title="View Detail"><ExternalLink className="w-4 h-4" /></span>
            </Link>
          </div>
        )
      }
    }
  ]

  return (
    <div className="flex flex-col bg-card shadow-sm border border-border/50 rounded-2xl overflow-hidden p-2">
      <DataTable 
        columns={columns} 
        data={translocations} 
        rowLabel="translocations"
        totalCount={translocationCount}
        page={Number(data?.meta?.page ?? page)}
        perPage={Number(data?.meta?.per_page ?? perPage)}
        hasNext={hasNext}
        hasPrevious={hasPrevious}
        onPageChange={setPage}
        onPerPageChange={(value) => {
          setPerPage(value)
          setPage(1)
        }}
        filename={`translocations_${sampleId}.csv`} 
        getRowClassName={findingRowClass}
        renderToolbar={(table) => (
          <>
            <BulkActionDropdown 
              selectedCount={Object.keys(table.getState().rowSelection).length} 
              actions={translocationBulkActions}
              isPending={bulkAction.isPending}
              onAction={(action) => bulkAction.mutateAsync({
                action,
                resourceIds: table.getSelectedRowModel().rows.map((row: any) => String(row.original._id)),
              })}
            />
          </>
        )}
        renderExportButton={() => (
            <ServerCsvButton
              endpoint={`/samples/${sampleId}/small-variants/exports/translocs/context`}
              fallbackFilename={`${sampleId}.filtered.translocations.csv`}
              label="Export to CSV"
            />
        )}
      />
    </div>
  )
}
