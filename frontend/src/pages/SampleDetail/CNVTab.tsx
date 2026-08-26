import { useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { AlertTriangle, ExternalLink, Image as ImageIcon, RotateCw } from "lucide-react"
import { DataTable } from "@/components/data-table/DataTable"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { BulkActionDropdown } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import { findingRowClass, normalizedCallerList, statusLabels } from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { findingBulkActionOptions } from "@/lib/finding-actions"
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { sampleFileName, hasSampleFile } from "@/lib/sample-shape"
import { apiPath } from "@/lib/runtime-paths"
import { gensSampleUrl } from "@/lib/external-links"
import { ResizableSplitPane } from "@/components/layout/ResizableSplitPane"
import { Button } from "@/components/ui/button"
import { RotatableImage } from "@/components/detail/RotatableImage"
import { ArtefactFrequencyBadges, CallerBadges, StatusBadges } from "@/lib/variant-ui"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"
import { AnalysisTableCard } from "./AnalysisTableCard"

function cnvRatio(cnv: any): number | null {
  const raw = cnv?.ratio ?? cnv?.log2
  if (raw === null || raw === undefined || raw === "") return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

function cnvCopyNumber(cnv: any): number | null {
  const ratio = cnvRatio(cnv)
  return ratio === null ? null : 2 * Math.pow(2, ratio)
}

function purityAdjustedCopyNumber(cnv: any, purity: unknown): number | null {
  const ratio = cnvRatio(cnv)
  const copyNumber = cnvCopyNumber(cnv)
  const purityValue = Number(purity)
  if (ratio === null || copyNumber === null || !Number.isFinite(purityValue) || purityValue <= 0) return null
  return ratio > 0 ? copyNumber / purityValue : copyNumber * purityValue
}

function structuralReadEvidence(cnv: any): string {
  const value = cnv?.SR ?? cnv?.sr ?? cnv?.INFO?.SR
  if (Array.isArray(value)) return value.length ? value.join(",") : "-"
  return value === null || value === undefined || value === "" ? "-" : String(value)
}

function artefactExportValue(cnv: any): string {
  return Object.keys(cnv || {})
    .filter((key) => key.startsWith("AFRQ_"))
    .map((key) => {
      const label = key.slice("AFRQ_".length)
      const frequency = Number(cnv[key])
      if (!Number.isFinite(frequency)) return ""
      const count = cnv[`ACOUNT_${label}`]
      const countText = count === null || count === undefined || count === "" ? "" : ` (${count} cases)`
      return `${label}: ${(frequency * 100).toFixed(1)}%${countText}`
    })
    .filter(Boolean)
    .join(" | ")
}

export function CNVTab({ sampleId, header }: { sampleId: string; header?: ReactNode }) {
  const controlsQuery = useApplicationModules()
  const cnvBulkActions = findingBulkActionOptions("cnv", {
    tieringEnabled: tieringIsEnabled(controlsQuery.data, "cnv"),
  })
  const bulkAction = useBulkFindingAction(sampleId, "cnv")
  const location = useLocation()
  const [profileRotation, setProfileRotation] = useState(0)
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
  const gensUrl = gensSampleUrl(sample.name)

  const columns: ColumnDef<any, any>[] = [
    {
      id: "select",
      meta: { headerClassName: "text-center w-8 border-r", cellClassName: "text-center w-8 border-r" },
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
          <div className="leading-tight">
            <div className="max-w-[120px] wrap-break-word font-medium text-primary" title={primaryGenes.join(', ')}>
              {primaryGenes.join(', ') || "-"}
            </div>
            {otherGenesCount > 0 && (
              <div className="type-table-value leading-tight text-muted-foreground">
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
          <div className="flex flex-col gap-0.5 leading-tight">
            <span className="type-table-value w-max rounded bg-muted px-1.5 py-0.5">{region}</span>
            <span className="type-table-value text-muted-foreground">{Math.abs(cnv.size).toLocaleString()} bp</span>
          </div>
        )
      }
    },
    {
      id: "callers",
      header: "Callers",
      accessorFn: (row) => normalizedCallerList(row.callers).join(", "),
      cell: ({ row }) => <CallerBadges value={row.original.callers} />
    },
    {
      id: "copy_number",
      header: "Copy Number",
      accessorFn: (row) => cnvCopyNumber(row),
      cell: ({ row }) => {
        const cnv = row.original
        const ratio = cnvRatio(cnv)
        const copyNumber = cnvCopyNumber(cnv)
        if (ratio === null || copyNumber === null) return <span className="text-muted-foreground">-</span>
        const isGain = ratio > 0
        return (
          <div className="flex items-center gap-2 leading-tight">
            <span className={`type-table-value-emphasis ${isGain ? "text-fail" : "text-tier3"}`}>
              {copyNumber.toFixed(2)}
            </span>
            <span className="type-table-value text-muted-foreground">({ratio.toFixed(2)})</span>
          </div>
        )
      }
    },
    {
      id: "purity",
      header: sample.purity ? `Purity ${sample.purity}` : "Purity",
      accessorFn: (row) => purityAdjustedCopyNumber(row, sample.purity),
      enableSorting: false,
      cell: ({ row }) => {
        const adjusted = purityAdjustedCopyNumber(row.original, sample.purity)
        return <span className="type-table-value text-muted-foreground">{adjusted === null ? "-" : adjusted.toFixed(2)}</span>
      }
    },
    {
      id: "sr",
      header: "SR (ref/alt)",
      accessorFn: (row) => structuralReadEvidence(row),
      cell: ({ row }) => <span className="type-table-value text-muted-foreground">{structuralReadEvidence(row.original)}</span>,
    },
    {
      id: "status",
      header: "Status",
      accessorFn: (row) => [statusLabels(row), row.noteworthy ? "Noteworthy" : "", row.NORMAL ? "Normal" : ""].filter(Boolean).join(" | "),
      meta: {
        exportValue: (row: any) => [statusLabels(row), row.noteworthy ? "Noteworthy" : "", row.NORMAL ? "Normal" : ""].filter(Boolean).join(" | "),
      },
      cell: ({ row }) => <StatusBadges finding={row.original} />,
    },
    {
      id: "artefact",
      header: "Artefact",
      accessorFn: artefactExportValue,
      meta: { exportValue: artefactExportValue },
      cell: ({ row }) => <ArtefactFrequencyBadges finding={row.original} />,
    },
    {
      id: "actions",
      header: "",
      meta: { headerClassName: "w-8 min-w-8 max-w-8 pr-1", cellClassName: "w-8 min-w-8 max-w-8 pr-1" },
      cell: ({ row }) => {
        return (
          <div className="flex items-center justify-start">
            <AppTooltip
              context="Table action"
              label="View CNV details"
              content="Open the complete CNV record, evidence, comments, and classification controls."
            >
              <Link
                to={`/samples/${sampleId}/cnv/${row.original._id}`}
                state={{ from: `${location.pathname}${location.search}` }}
                aria-label="View CNV details"
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

  const tablePane = (
    <AnalysisTableCard header={header}>
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
              <BulkActionDropdown
                selectedCount={Object.keys(table.getState().rowSelection).length}
                actions={cnvBulkActions}
                isPending={bulkAction.isPending}
                onAction={(action) => bulkAction.mutateAsync({
                  action,
                  resourceIds: table.getSelectedRowModel().rows.map((row: any) => String(row.original._id)),
                })}
              />
            )}
            renderExportButton={() => (
              <ServerCsvButton
                endpoint={`/samples/${sampleId}/cnvs/exports/context`}
                fallbackFilename={`${sampleId}.filtered.cnvs.csv`}
                label="Export to CSV"
              />
            )}
          />
    </AnalysisTableCard>
  )

  const profilePane = hasCnvImage ? (
    <div className="glass-card flex h-full w-full min-w-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/50 bg-muted/50 p-3">
        <h4 className="flex items-center gap-2 text-sm font-semibold">
          <ImageIcon className="size-4" /> CNV Profile
        </h4>
        <div className="flex items-center gap-2">
          <span className="text-xs type-numeric text-muted-foreground">{profileRotation}°</span>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            title={profileRotation === 0 ? "Rotate profile 90 degrees" : "Restore original orientation"}
            aria-label={profileRotation === 0 ? "Rotate CNV profile 90 degrees" : "Restore CNV profile orientation"}
            onClick={() => setProfileRotation((rotation) => rotation === 0 ? 90 : 0)}
          >
            <RotateCw aria-hidden="true" />
          </Button>
        </div>
      </div>
      <div className="flex min-h-72 flex-1 flex-col bg-muted/10 p-3">
        <RotatableImage
          key={cnvProfileName}
          src={apiPath(`/samples/${sampleId}/plots/${cnvProfileName}`)}
          href={apiPath(`/samples/${sampleId}/plots/${cnvProfileName}`)}
          alt={`CNV profile for ${sample.name || sampleId}`}
          rotation={profileRotation}
          fit="width"
          className="p-2"
        />
        {gensUrl ? (
          <div className="mt-3 flex justify-center">
            <a href={gensUrl} target="_blank" rel="noreferrer" className="rounded bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-primary/20">
              Open in GENS
            </a>
          </div>
        ) : null}
      </div>
    </div>
  ) : null

  return (
    <div className="flex flex-col space-y-4 pb-4">
      {profilePane ? (
        <ResizableSplitPane
          primary={tablePane}
          secondary={profilePane}
          storageKey="coyote3:cnv-profile-split"
          initialPrimarySize={65}
          minPrimarySize={35}
          maxPrimarySize={80}
          separatorLabel="Resize CNV table and profile panes"
        />
      ) : tablePane}
    </div>
  )
}
