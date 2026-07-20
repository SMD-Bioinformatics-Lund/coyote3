import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { AlertTriangle, ExternalLink, Image as ImageIcon } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { BulkActionDropdown, BulkActionOption } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import { findingRowClass, statusLabels } from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { sampleFileName, hasSampleFile } from "@/lib/sample-shape"
import { apiPath } from "@/lib/runtime-paths"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"

const cnvBulkActions: BulkActionOption[] = [
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
  { value: "noteworthy", label: "Mark Noteworthy" },
  { value: "unnoteworthy", label: "Unmark Noteworthy" },
]

export function CNVTab({ sampleId }: { sampleId: string }) {
  const bulkAction = useBulkFindingAction(sampleId, "cnv")
  const location = useLocation()
  const {
    page,
    perPage,
    sortParam,
    debouncedSearchText,
    tableProps,
  } = useClinicalTableState({ prefix: "cnv", tab: "cnvs" })
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-cnvs", sampleId, page, perPage, debouncedSearchText, sortParam],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      })
      if (debouncedSearchText) params.set("q", debouncedSearchText)
      if (sortParam) params.set("sort", sortParam)
      return api.get(`/samples/${sampleId}/cnvs?${params.toString()}`).then(res => res.data)
    },
    placeholderData: (previousData) => previousData,
    staleTime: CLINICAL_TABLE_STALE_MS,
    gcTime: CLINICAL_TABLE_CACHE_MS,
  })

  if (isLoading) return <AppLoader label="Loading CNVs" />
  if (error) return <div className="text-destructive p-4 flex gap-2"><AlertTriangle /> Error loading CNVs</div>

  const cnvs = data?.display_sections_data?.cnvs || data?.cnvs || []
  const cnvCount = Number(data?.meta?.count ?? cnvs.length)
  const hasNext = Boolean(data?.meta?.has_next)
  const hasPrevious = Boolean(data?.meta?.has_previous)
  const sample = data?.sample || {}
  const cnvProfileName = sampleFileName(sample, "cnvprofile")
  const hasCnvImage = hasSampleFile(sample, "cnvprofile") && cnvProfileName

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
      id: "genes",
      header: "Genes",
      accessorFn: (row) => row.genes?.filter((g: any) => g.class).map((g: any) => g.gene).join(', ') || "",
      cell: ({ row }) => {
        const genesList = row.original.genes || []
        const primaryGenes = genesList.filter((g: any) => g.class).map((g: any) => g.gene)
        const otherGenesCount = genesList.length - primaryGenes.length
        return (
          <div>
            <div className="font-bold text-primary max-w-[150px] truncate" title={primaryGenes.join(', ')}>
              {primaryGenes.join(', ') || "-"}
            </div>
            {otherGenesCount > 0 && (
              <div className="text-[11px] text-muted-foreground mt-0.5">
                + {otherGenesCount} other genes
              </div>
            )}
          </div>
        )
      }
    },
    {
      id: "region",
      header: "Region & Size",
      accessorFn: (row) => `${row.chr}:${row.start}-${row.end}`,
      cell: ({ row }) => {
        const cnv = row.original
        const region = `${cnv.chr}:${cnv.start}-${cnv.end}`
        return (
          <div className="flex flex-col gap-1">
            <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded w-max">{region}</span>
            <span className="text-xs text-muted-foreground">{Math.abs(cnv.size).toLocaleString()} bp</span>
          </div>
        )
      }
    },
    {
      id: "callers",
      header: "Callers",
      accessorFn: (row) => Array.isArray(row.callers) ? row.callers.join(', ') : row.callers,
      cell: ({ row }) => {
        const c = row.original.callers
        return <span className="text-xs uppercase font-medium text-muted-foreground">{c ? (Array.isArray(c) ? c.join(', ') : c) : "-"}</span>
      }
    },
    {
      id: "copy_number",
      header: "Copy Number",
      accessorFn: (row) => (2 * Math.pow(2, row.ratio)).toFixed(2),
      cell: ({ row }) => {
        const cnv = row.original
        const copyNumber = (2 * Math.pow(2, cnv.ratio)).toFixed(2)
        const isGain = cnv.ratio > 0
        return (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className={`font-mono font-bold ${isGain ? 'text-fail' : 'text-tier3'}`}>
                {copyNumber}
              </span>
              <span className="text-[11px] text-muted-foreground">({Number(cnv.ratio).toFixed(2)})</span>
            </div>
            {sample.purity && (
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Adj Purity: {isGain ? (Number(copyNumber) * 1 / sample.purity).toFixed(2) : (Number(copyNumber) * sample.purity).toFixed(2)}
              </div>
            )}
          </div>
        )
      }
    },
    {
      id: "status_artefact",
      header: "Status / Artefact",
      accessorFn: (row) => {
        const artefacts = Object.keys(row)
          .filter((key) => key.startsWith("AFRQ_"))
          .map((key) => `${key.split("_")[1]} ${(Number(row[key]) * 100).toFixed(1)}%`)
        return [statusLabels(row), row.noteworthy ? "Noteworthy" : "", ...artefacts].filter(Boolean).join(" | ")
      },
      meta: {
        exportValue: (row: any) => {
          const artefacts = Object.keys(row)
            .filter((key) => key.startsWith("AFRQ_"))
            .map((key) => `${key.split("_")[1]} ${(Number(row[key]) * 100).toFixed(1)}%`)
          return [statusLabels(row), row.noteworthy ? "Noteworthy" : "", ...artefacts].filter(Boolean).join(" | ")
        },
      },
      cell: ({ row }) => {
        const cnv = row.original
        const isInteresting = cnv.interesting
        const isFp = cnv.fp
        const isNoteworthy = cnv.noteworthy
        const artefactKeys = Object.keys(cnv).filter(k => k.startsWith('AFRQ_'))

        return (
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-1">
              {isInteresting && <span className="w-max rounded bg-pass px-1.5 py-0.5 text-[11px] font-bold uppercase text-primary-foreground">Report</span>}
              {isFp && <span className="w-max rounded bg-destructive px-1.5 py-0.5 text-[11px] font-bold uppercase text-destructive-foreground">False Positive</span>}
              {isNoteworthy && <span className="w-max rounded bg-warn px-1.5 py-0.5 text-[11px] font-bold uppercase text-primary-foreground">Noteworthy</span>}
            </div>
            <div className="flex flex-wrap gap-1">
              {artefactKeys.map(key => {
                const label = key.split('_')[1]
                const percent = (cnv[key] * 100).toFixed(1)
                return (
                  <span key={key} className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase text-primary-foreground ${
                    Number(percent) >= 1 ? 'bg-tier3' : Number(percent) >= 0.1 ? 'bg-tier2' : 'bg-pass'
                  }`} title={`${percent}% Artefact Frequency`}>
                    {label}
                  </span>
                )
              })}
            </div>
          </div>
        )
      }
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        return (
          <div className="flex items-center gap-1">
            <VariantActionButtons sampleId={sampleId} resourceType="cnv" variant={row.original} compact />
            <Link
              to={`/samples/${sampleId}/cnv/${row.original._id}`}
              state={{ from: `${location.pathname}${location.search}` }}
              className="inline-block rounded-md bg-primary/10 p-1.5 text-primary shadow-sm transition-colors duration-100 hover:bg-primary hover:text-primary-foreground"
            >
              <span title="View Detail"><ExternalLink className="w-4 h-4" /></span>
            </Link>
          </div>
        )
      }
    }
  ]

  return (
    <div className="space-y-4 flex flex-col">
      <div className="flex flex-col xl:flex-row gap-4 pb-4">
        {hasCnvImage && (
          <div className="glass-card w-full xl:w-2/5 flex flex-col overflow-hidden h-[600px]">
            <div className="bg-muted/50 p-3 border-b border-border/50 flex justify-between items-center">
              <h4 className="font-semibold text-sm flex items-center gap-2">
                <ImageIcon className="w-4 h-4" /> CNV Profile
              </h4>
            </div>
            <div className="p-4 flex flex-col items-center justify-center bg-muted/10 flex-1 overflow-auto">
              <img
                src={apiPath(`/samples/${sampleId}/plots/${cnvProfileName}?rotated=true`)}
                alt="CNV Profile"
                className="max-w-full rounded shadow-sm border border-border"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
              <div className="mt-4 flex gap-2">
                <a href={`http://gens.coyote.local/${sample.name}`} target="_blank" rel="noreferrer" className="rounded bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-primary/20">
                  Open in Gens
                </a>
              </div>
            </div>
          </div>
        )}

        <div className={`glass-card w-full ${hasCnvImage ? 'xl:w-3/5' : 'w-full'} flex flex-col overflow-hidden p-2`}>
          <DataTable
            columns={columns}
            data={cnvs}
            rowLabel="CNVs"
            totalCount={cnvCount}
            page={Number(data?.meta?.page ?? page)}
            perPage={Number(data?.meta?.per_page ?? perPage)}
            hasNext={hasNext}
            hasPrevious={hasPrevious}
            {...tableProps}
            filename={`cnvs_${sampleId}.csv`}
            getRowClassName={findingRowClass}
            renderToolbar={(table) => (
              <>
                <BulkActionDropdown
                  selectedCount={Object.keys(table.getState().rowSelection).length}
                  actions={cnvBulkActions}
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
                  endpoint={`/samples/${sampleId}/cnvs/exports/context`}
                  fallbackFilename={`${sampleId}.filtered.cnvs.csv`}
                  label="Export to CSV"
                />
            )}
          />
        </div>
      </div>
    </div>
  )
}
