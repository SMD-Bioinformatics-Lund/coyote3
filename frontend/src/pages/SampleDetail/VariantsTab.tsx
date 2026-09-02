import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { DataTable } from "@/components/data-table/DataTable"
import { BulkActionDropdown } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, ExternalLink } from "lucide-react"
import { ConsequenceBadges, FilterFlagBadges, StatusBadges, TierBadge } from "@/lib/variant-ui"
import { filterFlags, findingRowClass, statusLabels, tierValue } from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { findingBulkActionOptions } from "@/lib/finding-actions"
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import { igvLoadUrl } from "@/lib/external-links"
import { tieredVariantSearchPath } from "@/lib/variant-routing"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"
import { AnalysisTableCard } from "./AnalysisTableCard"
import { HotspotIndicator } from "@/components/detail/HotspotIndicator"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { formatPopulationFrequency, hotspotExportValue } from "@/lib/variant-table-format"

const variantClassShort: Record<string, string> = {
  SNV: "SNV",
  deletion: "DEL",
  DELETION: "DEL",
  insertion: "INS",
  INSERTION: "INS",
  indel: "INDEL",
  INDEL: "INDEL",
  substitution: "SUB",
}

function compactVariantClass(value: unknown) {
  const key = String(value || "").trim()
  return variantClassShort[key] || key.toUpperCase() || "-"
}

export function VariantsTab({
  sampleId,
  intent,
  header,
  filterPanel,
}: {
  sampleId: string
  intent: "somatic" | "germline"
  header?: ReactNode
  filterPanel?: ReactNode
}) {
  const controlsQuery = useApplicationModules()
  const variantBulkActions = findingBulkActionOptions("small_variant", {
    tieringEnabled: tieringIsEnabled(controlsQuery.data, "small_variant"),
  })
  const bulkAction = useBulkFindingAction(sampleId, "small_variant")
  const location = useLocation()
  const tabId = intent === "germline" ? "germline-snvs" : "snvs"
  const {
    page,
    perPage,
    sortParam,
    debouncedSearchText,
    tableProps,
  } = useClinicalTableState({ prefix: `snv-${intent}`, tab: tabId })
  const { data, isLoading, error } = useQuery({
    queryKey: [
      "sample-variants",
      sampleId,
      page,
      perPage,
      debouncedSearchText,
      sortParam,
      intent,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      })
      if (debouncedSearchText) params.set("q", debouncedSearchText)
      if (sortParam) params.set("sort", sortParam)
      params.set("intent", intent)
      return api.get(`/samples/${sampleId}/small-variants?${params.toString()}`).then(res => res.data)
    },
    placeholderData: (previousData) => previousData,
    staleTime: CLINICAL_TABLE_STALE_MS,
    gcTime: CLINICAL_TABLE_CACHE_MS,
  })
  const { data: filterFlagMetadata } = useQuery({
    queryKey: ["filter-flag-metadata"],
    queryFn: () => api.get("/public/filter-flags/metadata").then(res => res.data),
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) return <AppLoader label="Loading variants" />
  if (error) return <div className="text-destructive p-4 flex gap-2"><AlertTriangle /> Error loading variants</div>

  const variants = data?.display_sections_data?.snvs || []
  const oncokbGeneMap = data?.oncokb_gene_map || {}
  const oncokbActionableGeneMap = data?.oncokb_actionable_gene_map || {}
  const clinpgxGeneMap = data?.clinpgx_gene_map || {}
  const variantCount = Number(data?.meta?.count ?? variants.length)
  const hasNext = Boolean(data?.meta?.has_next)
  const hasPrevious = Boolean(data?.meta?.has_previous)
  const firstGt = variants?.[0]?.GT || []
  const samplePayload = data?.sample || {}
  const caseSample = firstGt.find((gt: any) => gt.type === "case")?.sample || samplePayload.case_id || samplePayload.case?.id
  const controlSample = firstGt.find((gt: any) => gt.type === "control")?.sample || samplePayload.control_id || samplePayload.control?.id
  const hasControlColumn = samplePayload.paired === true
  const assayGroup = String(data?.assay_group || "").trim()

  const columns: ColumnDef<any, any>[] = [
    {
      id: "select",
      meta: {
        headerClassName: "w-8 min-w-8 max-w-8 border-r",
        cellClassName: "w-8 min-w-8 max-w-8 border-r",
      },
      header: ({ table }) => (
        <div className="flex w-full items-center justify-center ">
          <input
            type="checkbox"
            checked={table.getIsAllPageRowsSelected()}
            ref={(element) => {
              if (element) {
                element.indeterminate =
                  table.getIsSomePageRowsSelected() &&
                  !table.getIsAllPageRowsSelected()
              }
            }}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            className="table-checkbox"
            aria-label="Select all rows on this page"
          />
        </div>
      ),
      cell: ({ row }) => (
        <div className="flex w-full items-center justify-center">
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            className="table-checkbox"
            aria-label="Select row"
          />
        </div>
      ),
      enableSorting: false,
    },
    {
      id: "badges",
      header: "Info",
      accessorFn: (row) => statusLabels(row),
      meta: {
        exportValue: statusLabels,
        headerClassName: "w-[4.5rem] min-w-[4.5rem] max-w-[4.5rem]",
        cellClassName: "w-[4.5rem] min-w-[4.5rem] max-w-[4.5rem]",
      },
      enableSorting: false,
      size: 72,
      minSize: 72,
      maxSize: 72,
      cell: ({ row }) => {
        const symbol = row.original.INFO?.selected_CSQ?.SYMBOL
        return (
          <StatusBadges
            finding={row.original}
            gene={symbol}
            hasOncoKbCancerGene={Boolean(oncokbGeneMap?.[symbol])}
            hasOncoKbActionable={Boolean(oncokbActionableGeneMap?.[symbol])}
            hasClinPgxGene={Boolean(clinpgxGeneMap?.[symbol])}
            clinPgxRecord={clinpgxGeneMap?.[symbol]}
          />
        )
      }
    },
    {
      accessorKey: "INFO.selected_CSQ.SYMBOL",
      id: "gene",
      header: "Gene",
      meta: { headerClassName: "w-20 min-w-20", cellClassName: "w-20 min-w-20" },
      cell: ({ row }) => {
        const csq = row.original.INFO?.selected_CSQ || {}
        const displayGene = csq.display_symbol || csq.SYMBOL
        const resolvedGene = csq.SYMBOL
        return (
          <GeneWithOncoKbBadge
            gene={resolvedGene}
            displayGene={displayGene}
            resolvedGene={resolvedGene}
            hgncId={csq.HGNC_ID}
            showOncoKbBadge={false}
            geneTo={tieredVariantSearchPath(resolvedGene || displayGene, assayGroup)}
            className="max-w-full"
          />
        )
      }
    },
    {
      id: "hgvs",
      header: "HGVS",
      accessorFn: (row) => `${row.INFO?.selected_CSQ?.HGVSc || ""} ${row.INFO?.selected_CSQ?.HGVSp || ""}`,
      meta: { headerClassName: "w-44 min-w-36 max-w-48", cellClassName: "w-44 min-w-36 max-w-48" },
      cell: ({ row }) => {
        const csq = row.original.INFO?.selected_CSQ || {}
        return (
          <div className="flex min-w-0 flex-col gap-0 leading-[1.2] text-foreground justify-items-center">
            <ExpandableText text={csq.HGVSc || "-"} maxLength={32} className="type-table-value leading-[1.2] text-foreground/80" />
            <ExpandableText text={csq.HGVSp && csq.HGVSp !== "-" ? csq.HGVSp : "-"} maxLength={32} className="type-table-value-emphasis leading-[1.2] text-foreground" />
          </div>
        )
      }
    },
    {
      id: "exon",
      header: "Exon",
      accessorFn: (row) => row.INFO?.selected_CSQ?.EXON || "-",
      meta: { headerClassName: "w-10 min-w-8 max-w-12", cellClassName: "w-10 min-w-8 max-w-12" },
      cell: ({ row }) => {
        const exon = row.original.INFO?.selected_CSQ?.EXON
        return <span className="type-table-value">{exon || "-"}</span>
      }
    },
    {
      id: "intron",
      header: "Intron",
      accessorFn: (row) => row.INFO?.selected_CSQ?.INTRON || "-",
      meta: { headerClassName: "w-12 min-w-10 max-w-14", cellClassName: "w-12 min-w-10 max-w-14" },
      cell: ({ row }) => {
        const intron = row.original.INFO?.selected_CSQ?.INTRON
        return <span className="type-table-value">{intron || "-"}</span>
      }
    },
    {
      id: "type",
      header: "Type",
      accessorFn: (row) => row.variant_class || "-",
      meta: { headerClassName: "w-16", cellClassName: "w-16" },
      cell: ({ row }) => {
        const raw = row.original.variant_class || "-"
        return <span className="type-table-value-emphasis uppercase" title={raw}>{compactVariantClass(raw)}</span>
      }
    },
    {
      id: "indel_size",
      header: "Indel Size",
      accessorFn: (row) => row.INFO?.SVLEN || "-",
      meta: { headerClassName: "w-16", cellClassName: "w-16" },
      cell: ({ row }) => <span className="type-table-value text-muted-foreground">{row.original.INFO?.SVLEN || "-"}</span>
    },
    {
      id: "consequence",
      header: "Consequence",
      meta: { headerClassName: "w-32 min-w-28 max-w-44", cellClassName: "w-32 min-w-28 max-w-44" },
      accessorFn: (row) => {
        const c = row.original.INFO?.selected_CSQ?.Consequence
        if (!c) return ""
        return Array.isArray(c) ? c.join(',') : c
      },
      cell: ({ row }) => {
        const c = row.original.INFO?.selected_CSQ?.Consequence
        let consequences: string[] = []
        if (c) {
          consequences = Array.isArray(c) ? c : String(c).split("&")
        }
        if (!consequences.length) consequences = ["-"]
        return (
          <ConsequenceBadges value={consequences} translations={data?.vep_conseq_translations} />
        )
      }
    },
    {
      id: "popfreq",
      header: "PopFreq (%)",
      accessorFn: (row) => row.gnomad_frequency ?? null,
      meta: { headerClassName: "w-16 min-w-16 max-w-20", cellClassName: "w-16 min-w-16 max-w-20" },
      cell: ({ row }) => {
        const freq = row.original.gnomad_frequency
        return <span className="type-table-value type-numeric whitespace-nowrap">{formatPopulationFrequency(freq)}</span>
      }
    },
    {
      id: "hotspot",
      header: () => (
        <AppTooltip
          context="Column"
          label="Hotspot"
          content="Indicates whether the variant matches a known clinically relevant hotspot."
        >
          <span className="cursor-help whitespace-nowrap">HS</span>
        </AppTooltip>
      ),
      accessorFn: hotspotExportValue,
      meta: {
        exportValue: hotspotExportValue,
        headerClassName: "w-8 min-w-8 max-w-10",
        cellClassName: "w-8 min-w-8 max-w-10",
      },
      cell: ({ row }) => <HotspotIndicator variant={row.original} />,
    },
    {
      id: "tier",
      accessorFn: tierValue,
      meta: { exportValue: (row: any) => tierValue(row) === 999 ? "" : tierValue(row), headerClassName: "w-8 min-w-8 max-w-10", cellClassName: "w-8 min-w-8 max-w-10" },
      header: "Tier",
      size: 56,
      cell: ({ row }) => {
        const tier = tierValue(row.original)
        if (tier === 999) return <TierBadge tier={tier} />
        return (
          <Link
            to={`/variants/reported/${row.original._id}/${tier}`}
            aria-label={`Show reported samples for this Tier ${tier} variant`}
          >
            <TierBadge tier={tier} className="hover:ring-2 hover:ring-ring/40" />
          </Link>
        )
      }
    },
    {
      id: "chrpos",
      header: "Chr:Pos",
      accessorFn: (row) => `${row.CHROM}:${row.POS}`,
      meta: { headerClassName: "w-24 min-w-24 max-w-28", cellClassName: "w-24 min-w-24 max-w-28" },
      cell: ({ row }) => {
        const v = row.original
        const loc = `${v.CHROM}:${v.POS}`
        const igvUrl = igvLoadUrl(sampleId, loc)
        return (
          igvUrl ? (
            <a href={igvUrl} target="_blank" rel="noreferrer" className="type-table-value inline-block whitespace-nowrap rounded border border-border bg-muted px-0.5 py-0 text-muted-foreground shadow-sm transition-colors hover:bg-muted/80 hover:text-foreground dark:bg-muted/60">
              {loc}
            </a>
          ) : (
            <span className="type-table-value inline-block whitespace-nowrap rounded border border-border bg-muted px-0.5 py-0 text-muted-foreground">{loc}</span>
          )
        )
      }
    },
    {
      id: "flags",
      header: "Flags",
      accessorFn: (row) => filterFlags(row.FILTER).join(", "),
      meta: { exportValue: (row: any) => filterFlags(row.FILTER).join(", "), headerClassName: "w-36 min-w-28 max-w-48", cellClassName: "w-36 min-w-28 max-w-48" },
      cell: ({ row }) => {
        return <FilterFlagBadges value={row.original.FILTER} metadata={filterFlagMetadata} />
      }
    },
    {
      id: "case_vaf",
      header: caseSample ? `Case % (${caseSample})` : "Case %",
      accessorFn: (row) => {
        const caseGt = row.GT?.find((gt: any) => gt.type === "case")
        return caseGt ? caseGt.AF : 0
      },
      meta: {
        headerClassName: "w-28 min-w-28 max-w-30",
        cellClassName: "w-28 min-w-28 max-w-30",
        exportValue: (row: any) => {
          const gt = row.GT?.find((item: any) => item.type === "case")
          return gt ? `${(gt.AF * 100).toFixed(1)}% (${gt.VD}/${gt.DP})` : ""
        },
      },
      cell: ({ row }) => {
        const caseGt = row.original.GT?.find((gt: any) => gt.type === "case")
        return (
          <div className="type-table-value flex items-center gap-1 whitespace-nowrap text-foreground" title={caseGt ? `Case ${(caseGt.AF * 100).toFixed(1)} (${caseGt.VD}/${caseGt.DP})` : "Case -"}>
            <span className="type-allele-frequency">{caseGt ? `${(caseGt.AF * 100).toFixed(1)}` : "-"}</span>
            <span className="font-normal text-foreground">{caseGt ? `(${caseGt.VD}/${caseGt.DP})` : "-"}</span>
          </div>
        )
      }
    },
    ...(hasControlColumn ? [
      {
        id: "control_vaf",
        header: controlSample ? `Control % (${controlSample})` : "Control %",
        accessorFn: (row: any) => {
          const ctrlGt = row.GT?.find((gt: any) => gt.type === "control")
          return ctrlGt ? ctrlGt.AF : 0
        },
        meta: {
          headerClassName: "w-28 min-w-28 max-w-30",
          cellClassName: "w-28 min-w-28 max-w-30",
          exportValue: (row: any) => {
            const gt = row.GT?.find((item: any) => item.type === "control")
            return gt ? `${(gt.AF * 100).toFixed(1)}% (${gt.VD}/${gt.DP})` : ""
          },
        },
        cell: ({ row }: any) => {
          const ctrlGt = row.original.GT?.find((gt: any) => gt.type === "control")
          return (
            <div className="type-table-value flex items-center gap-1 whitespace-nowrap text-foreground" title={ctrlGt ? `Control ${(ctrlGt.AF * 100).toFixed(1)}% (${ctrlGt.VD}/${ctrlGt.DP})` : "Control -"}>
              <span className="type-allele-frequency">{ctrlGt ? `${(ctrlGt.AF * 100).toFixed(1)}` : "-"}</span>
              <span className="font-normal text-foreground">{ctrlGt ? `(${ctrlGt.VD}/${ctrlGt.DP})` : "-"}</span>
            </div>
          )
        }
      },
    ] : []),
    {
      id: "actions",
      header: "",
      meta: { headerClassName: "w-8 min-w-8 max-w-8 pr-1", cellClassName: "w-8 min-w-8 max-w-8 pr-1" },
      cell: ({ row }) => {
        return (
          <div className="flex items-center justify-start">
            <AppTooltip
              context="Table action"
              label="View variant details"
              content="Open the complete variant record, evidence, comments, and classification controls."
            >
              <Link
                to={`/samples/${sampleId}/variant/${row.original._id}`}
                state={{ from: `${location.pathname}${location.search}` }}
                aria-label="View variant details"
                className="inline-block rounded-md bg-primary/10 p-0.5 text-primary shadow-sm transition-colors duration-100 hover:bg-primary hover:text-primary-foreground"
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
    <AnalysisTableCard header={header} filterPanel={filterPanel}>
      <DataTable
        columns={columns}
        data={variants || []}
        rowLabel="variants"
        totalCount={variantCount}
        page={Number(data?.meta?.page ?? page)}
        perPage={Number(data?.meta?.per_page ?? perPage)}
        hasNext={hasNext}
        hasPrevious={hasPrevious}
        {...tableProps}
        searchPlaceholder="Search variants, genes, HGVS, flags..."
        filename={`variants_${sampleId}.csv`}
        getRowClassName={findingRowClass}
        renderToolbar={(table) => (
          <>
            <BulkActionDropdown
              selectedCount={Object.keys(table.getState().rowSelection).length}
              actions={variantBulkActions}
              isPending={bulkAction.isPending}
              automaticTextAvailable
              onAction={(action, options) => bulkAction.mutateAsync({
                action,
                includeAutomaticText: options?.includeAutomaticText,
                resourceIds: table.getSelectedRowModel().rows.map((row: any) => String(row.original._id)),
              })}
            />
          </>
        )}
        renderExportButton={() => (
            <ServerCsvButton
              endpoint={`/samples/${sampleId}/small-variants/exports/snvs/context${
                debouncedSearchText ? `?q=${encodeURIComponent(debouncedSearchText)}` : ""
              }`}
              fallbackFilename={`${sampleId}.filtered.snvs.csv`}
              label="Export to CSV"
            />
        )}
      />
    </AnalysisTableCard>
  )
}
