import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "react-router-dom"
import { api } from "@/lib/api"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { DataTable } from "@/components/data-table/DataTable"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { BulkActionDropdown } from "@/components/data-table/BulkActionDropdown"
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton"
import { AppLoader } from "@/components/layout/AppLoader"
import { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, ExternalLink } from "lucide-react"
import { ConsequenceBadges, FilterFlagBadges, StatusBadges, TierBadge } from "@/lib/variant-ui"
import { filterFlags, findingRowClass, statusLabels, tierValue } from "@/lib/variant-helpers"
import { useBulkFindingAction } from "@/hooks/useFindingActions"
import { findingBulkActionOptions } from "@/lib/finding-actions"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import { igvLoadUrl } from "@/lib/external-links"
import { tieredVariantSearchPath } from "@/lib/variant-routing"
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState"

const variantBulkActions = findingBulkActionOptions("small_variant")

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

export function VariantsTab({ sampleId, intent }: { sampleId: string; intent: "somatic" | "germline" }) {
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
      id: "badges",
      header: "Info",
      accessorFn: (row) => statusLabels(row),
      meta: { exportValue: statusLabels, headerClassName: "w-24 min-w-24 max-w-24", cellClassName: "w-24 min-w-24 max-w-24" },
      enableSorting: false,
      size: 88,
      minSize: 82,
      maxSize: 96,
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
      meta: { headerClassName: "w-56 min-w-52", cellClassName: "w-56 min-w-52" },
      cell: ({ row }) => {
        const csq = row.original.INFO?.selected_CSQ || {}
        return (
          <div className="flex w-52 flex-col leading-tight">
            <ExpandableText text={csq.HGVSc || "-"} maxLength={28} className="text-[11px] leading-tight text-muted-foreground" />
            <ExpandableText text={csq.HGVSp && csq.HGVSp !== "-" ? csq.HGVSp : "-"} maxLength={28} className="text-[11px] font-semibold leading-tight text-foreground" />
          </div>
        )
      }
    },
    {
      id: "exon",
      header: "Exon",
      accessorFn: (row) => row.INFO?.selected_CSQ?.EXON || "-",
      meta: { headerClassName: "w-14", cellClassName: "w-14" },
      cell: ({ row }) => {
        const exon = row.original.INFO?.selected_CSQ?.EXON
        return <span className="text-[11px]">{exon || "-"}</span>
      }
    },
    {
      id: "intron",
      header: "Intron",
      accessorFn: (row) => row.INFO?.selected_CSQ?.INTRON || "-",
      meta: { headerClassName: "w-14", cellClassName: "w-14" },
      cell: ({ row }) => {
        const intron = row.original.INFO?.selected_CSQ?.INTRON
        return <span className="text-[11px]">{intron || "-"}</span>
      }
    },
    {
      id: "type",
      header: "Type",
      accessorFn: (row) => row.variant_class || "-",
      meta: { headerClassName: "w-16", cellClassName: "w-16" },
      cell: ({ row }) => {
        const raw = row.original.variant_class || "-"
        return <span className="text-[11px] font-bold uppercase" title={raw}>{compactVariantClass(raw)}</span>
      }
    },
    {
      id: "indel_size",
      header: "Indel Size",
      accessorFn: (row) => row.INFO?.SVLEN || "-",
      meta: { headerClassName: "w-16", cellClassName: "w-16" },
      cell: ({ row }) => <span className="text-[11px] text-muted-foreground">{row.original.INFO?.SVLEN || "-"}</span>
    },
    {
      id: "consequence",
      header: "Consequence",
      meta: { headerClassName: "w-36 min-w-32", cellClassName: "w-36 min-w-32" },
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
      accessorFn: (row) => row.gnomad_frequency || 0,
      meta: { headerClassName: "w-20", cellClassName: "w-20" },
      cell: ({ row }) => {
        const freq = row.original.gnomad_frequency
        return <span className="text-[11px]">{freq ? (freq * 100).toFixed(3) : "-"}</span>
      }
    },
    {
      id: "tier",
      accessorFn: tierValue,
      meta: { exportValue: (row: any) => tierValue(row) === 999 ? "" : tierValue(row), headerClassName: "w-14 min-w-14", cellClassName: "w-14 min-w-14" },
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
      meta: { headerClassName: "w-24 min-w-24", cellClassName: "w-24 min-w-24" },
      cell: ({ row }) => {
        const v = row.original
        const loc = `${v.CHROM}:${v.POS}`
        const igvUrl = igvLoadUrl(sampleId, loc)
        return (
          igvUrl ? (
            <a href={igvUrl} target="_blank" rel="noreferrer" className="inline-block rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground shadow-sm transition-colors hover:bg-muted/80 hover:text-foreground dark:bg-muted/60">
              {loc}
            </a>
          ) : (
            <span className="inline-block rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{loc}</span>
          )
        )
      }
    },
    {
      id: "flags",
      header: "Flags",
      accessorFn: (row) => filterFlags(row.FILTER).join(", "),
      meta: { exportValue: (row: any) => filterFlags(row.FILTER).join(", "), headerClassName: "w-56 min-w-48", cellClassName: "w-56 min-w-48" },
      cell: ({ row }) => {
        return <FilterFlagBadges value={row.original.FILTER} metadata={filterFlagMetadata} />
      }
    },
    {
      id: "case_vaf",
      header: caseSample ? `Case (${caseSample})` : "Case",
      accessorFn: (row) => {
        const caseGt = row.GT?.find((gt: any) => gt.type === "case")
        return caseGt ? caseGt.AF : 0
      },
      meta: {
        headerClassName: "w-28 min-w-24",
        cellClassName: "w-28 min-w-24",
        exportValue: (row: any) => {
          const gt = row.GT?.find((item: any) => item.type === "case")
          return gt ? `${(gt.AF * 100).toFixed(1)}% (${gt.VD}/${gt.DP})` : ""
        },
      },
      cell: ({ row }) => {
        const caseGt = row.original.GT?.find((gt: any) => gt.type === "case")
        return (
          <div className="flex items-center gap-1 text-[11px]" title={caseGt ? `Case ${(caseGt.AF * 100).toFixed(1)}% (${caseGt.VD}/${caseGt.DP})` : "Case -"}>
            <span className="font-bold">{caseGt ? `${(caseGt.AF * 100).toFixed(1)}%` : "-"}</span>
            <span className="text-muted-foreground">{caseGt ? `(${caseGt.VD}/${caseGt.DP})` : "-"}</span>
          </div>
        )
      }
    },
    ...(hasControlColumn ? [
      {
        id: "control_vaf",
        header: controlSample ? `Control (${controlSample})` : "Control",
        accessorFn: (row: any) => {
          const ctrlGt = row.GT?.find((gt: any) => gt.type === "control")
          return ctrlGt ? ctrlGt.AF : 0
        },
        meta: {
          headerClassName: "w-28 min-w-24",
          cellClassName: "w-28 min-w-24",
          exportValue: (row: any) => {
            const gt = row.GT?.find((item: any) => item.type === "control")
            return gt ? `${(gt.AF * 100).toFixed(1)}% (${gt.VD}/${gt.DP})` : ""
          },
        },
        cell: ({ row }: any) => {
          const ctrlGt = row.original.GT?.find((gt: any) => gt.type === "control")
          return (
            <div className="flex items-center gap-1 text-[11px]" title={ctrlGt ? `Control ${(ctrlGt.AF * 100).toFixed(1)}% (${ctrlGt.VD}/${ctrlGt.DP})` : "Control -"}>
              <span className="font-semibold text-foreground/70">{ctrlGt ? `${(ctrlGt.AF * 100).toFixed(1)}%` : "-"}</span>
              <span className="text-muted-foreground">{ctrlGt ? `(${ctrlGt.VD}/${ctrlGt.DP})` : "-"}</span>
            </div>
          )
        }
      },
    ] : []),
    {
      id: "actions",
      header: "Actions",
      meta: { headerClassName: "w-14", cellClassName: "w-14" },
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
    <div className="glass-card flex flex-col overflow-hidden p-3">
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
              onAction={(action) => bulkAction.mutateAsync({
                action,
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
    </div>
  )
}
