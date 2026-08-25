import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { AlertTriangle, ExternalLink } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { BulkActionDropdown } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import { ExpandableText } from "@/components/detail/ExpandableText"
import {
  ConsequenceBadges,
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
import { findingBulkActionOptions } from "@/lib/finding-actions"
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"
import { AnalysisTableCard } from "./AnalysisTableCard"

export function TranslocationsTab({ sampleId, header }: { sampleId: string; header?: ReactNode }) {
  const controlsQuery = useApplicationModules()
  const translocationBulkActions = findingBulkActionOptions("translocation", {
    tieringEnabled: tieringIsEnabled(controlsQuery.data, "translocation"),
  })
  const bulkAction = useBulkFindingAction(sampleId, "translocation")
  const location = useLocation()
  const {
    page,
    perPage,
    sortParam,
    debouncedSearchText,
    tableProps,
  } = useClinicalTableState({ prefix: "transloc", tab: "translocations" })
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-translocations", sampleId, page, perPage, debouncedSearchText, sortParam],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      })
      if (debouncedSearchText) params.set("q", debouncedSearchText)
      if (sortParam) params.set("sort", sortParam)
      return api.get(`/samples/${sampleId}/translocations?${params.toString()}`).then(res => res.data)
    },
    placeholderData: (previousData) => previousData,
    staleTime: CLINICAL_TABLE_STALE_MS,
    gcTime: CLINICAL_TABLE_CACHE_MS,
  })

  if (isLoading) return <AppLoader label="Loading translocations" />
  if (error) return <div className="text-destructive p-4 flex gap-2"><AlertTriangle /> Error loading Translocations</div>

  const translocations = data?.display_sections_data?.translocs || data?.translocations || []
  const translocationCount = Number(data?.meta?.count ?? translocations.length)
  const hasNext = Boolean(data?.meta?.has_next)
  const hasPrevious = Boolean(data?.meta?.has_previous)

  const columns: ColumnDef<any, any>[] = [
    {
      id: "select",
      meta: { headerClassName: "text-center w-8", cellClassName: "text-center w-8" },
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
          <span className="type-table-value text-muted-foreground">
            {position}
          </span>
        )
      }
    },
    {
      id: "type",
      header: "Type",
      accessorFn: translocationType,
      meta: { headerClassName: "min-w-48", cellClassName: "min-w-48" },
      cell: ({ row }) => (
        <ConsequenceBadges
          value={translocationType(row.original)}
          translations={data?.vep_conseq_translations}
          wide
        />
      ),
    },
    {
      id: "hgvs",
      header: "HGVS",
      accessorFn: (row) => {
        const ann = selectedTranslocationAnnotation(row)
        const hgvs = translocationHgvs(ann)
        return [hgvs.coding, hgvs.protein].filter(Boolean).join(" ")
      },
      meta: { headerClassName: "w-80 min-w-72", cellClassName: "w-80 min-w-72" },
      cell: ({ row }) => {
        const ann = selectedTranslocationAnnotation(row.original)
        const hgvs = translocationHgvs(ann)
        return (
          <div className="flex w-full max-w-80 flex-col leading-tight">
            <ExpandableText text={hgvs.coding || "-"} maxLength={42} className="type-table-value text-muted-foreground" />
            <ExpandableText text={hgvs.protein || "-"} maxLength={42} className="type-table-value-emphasis" />
          </div>
        )
      }
    },
    {
      id: "panel",
      header: "Panel",
      accessorFn: translocationPanelStatus,
      cell: ({ row }) => <span className="type-table-value text-muted-foreground">{translocationPanelStatus(row.original)}</span>
    },
    {
      id: "tier",
      header: "Tier",
      accessorFn: tierValue,
      meta: { exportValue: (row: any) => tierValue(row) === 999 ? "" : tierValue(row), headerClassName: "w-14 min-w-14", cellClassName: "w-14 min-w-14" },
      cell: ({ row }) => <TierBadge tier={tierValue(row.original)} />,
    },
    {
      id: "badges",
      header: "Status",
      meta: { exportValue: statusLabels, headerClassName: "w-24 min-w-24 max-w-24", cellClassName: "w-24 min-w-24 max-w-24" },
      accessorFn: (row) => statusLabels(row),
      cell: ({ row }) => <StatusBadges finding={row.original} />,
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        return (
          <div className="flex items-center gap-1">
            <VariantActionButtons
              sampleId={sampleId}
              resourceType="translocation"
              variant={row.original}
              compact
              showActionLabel
            />
            <AppTooltip
              context="Table action"
              label="View translocation details"
              content="Open the complete translocation record, transcript evidence, comments, and review controls."
            >
              <Link
                to={`/samples/${sampleId}/translocation/${row.original._id}`}
                state={{ from: `${location.pathname}${location.search}` }}
                aria-label="View translocation details"
                className="inline-block rounded-md bg-primary/10 p-0.5 text-primary shadow-sm transition-colors duration-100 hover:bg-primary hover:text-white"
              >
                <ExternalLink className="w-4 h-4" />
              </Link>
            </AppTooltip>
          </div>
        )
      }
    }
  ]

  return (
    <AnalysisTableCard header={header}>
      <DataTable
        columns={columns}
        data={translocations}
        rowLabel="translocations"
        totalCount={translocationCount}
        page={Number(data?.meta?.page ?? page)}
        perPage={Number(data?.meta?.per_page ?? perPage)}
        hasNext={hasNext}
        hasPrevious={hasPrevious}
        {...tableProps}
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
              endpoint={`/samples/${sampleId}/translocations/exports/context`}
              fallbackFilename={`${sampleId}.filtered.translocations.csv`}
              label="Export to CSV"
            />
        )}
      />
    </AnalysisTableCard>
  )
}
