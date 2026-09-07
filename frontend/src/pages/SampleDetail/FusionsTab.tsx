import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { AlertTriangle } from "lucide-react";
import { DataTable } from "@/components/data-table/DataTable";
import { DetailNavigationButton } from "@/components/data-table/DetailNavigationButton";
import { DETAIL_NAVIGATION_COLUMN_META } from "@/components/data-table/detail-navigation-column";
import { BulkActionDropdown } from "@/components/data-table/BulkActionDropdown";
import { ServerCsvButton } from "@/components/data-table/ServerCsvButton";
import { AppLoader } from "@/components/layout/AppLoader";
import { ColumnDef } from "@tanstack/react-table";
import { StatusBadges, TierBadge } from "@/lib/variant-ui";
import { FusionCallerBadges, FusionEffectBadge, FusionEvidenceBadges } from "@/lib/fusion-ui";
import {
  findingRowClass,
  fusionCallers,
  fusionGenes,
  selectedFusionCall,
  statusLabels,
  tierValue,
} from "@/lib/variant-helpers";
import { useBulkFindingAction } from "@/hooks/useFindingActions";
import { findingBulkActionOptions } from "@/lib/finding-actions";
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state";
import { tieredVariantSearchPath } from "@/lib/variant-routing";
import {
  CLINICAL_TABLE_CACHE_MS,
  CLINICAL_TABLE_STALE_MS,
  useClinicalTableState,
} from "@/hooks/useClinicalTableState";
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control";
import { AnalysisTableCard } from "./AnalysisTableCard";
import { createRowSelectionColumn } from "@/components/data-table/row-selection-column";
import { matchedKnowledgebaseGenes } from "@/lib/knowledgebase-markers";

export function FusionsTab({
  sampleId,
  header,
  filterPanel,
}: {
  sampleId: string;
  header?: ReactNode;
  filterPanel?: ReactNode;
}) {
  const controlsQuery = useApplicationModules();
  const fusionBulkActions = findingBulkActionOptions("fusion", {
    tieringEnabled: tieringIsEnabled(controlsQuery.data, "fusion"),
  });
  const bulkAction = useBulkFindingAction(sampleId, "fusion");
  const access = useCurrentUserAccess();
  const canManage = hasPermission(access.data, "fusion:manage");
  const location = useLocation();
  const { page, perPage, sortParam, debouncedSearchText, tableProps } = useClinicalTableState({
    prefix: "fusion",
    tab: "fusions",
  });
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-fusions", sampleId, page, perPage, debouncedSearchText, sortParam],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (debouncedSearchText) params.set("q", debouncedSearchText);
      if (sortParam) params.set("sort", sortParam);
      return api.get(`/samples/${sampleId}/fusions?${params.toString()}`).then((res) => res.data);
    },
    placeholderData: (previousData) => previousData,
    staleTime: CLINICAL_TABLE_STALE_MS,
    gcTime: CLINICAL_TABLE_CACHE_MS,
  });

  if (isLoading) return <AppLoader label="Loading fusions" />;
  if (error)
    return (
      <div className="text-destructive p-4 flex gap-2">
        <AlertTriangle /> Error loading Fusions
      </div>
    );

  const fusions = data?.fusions || [];
  const fusionCount = Number(data?.meta?.count ?? fusions.length);
  const hasNext = Boolean(data?.meta?.has_next);
  const hasPrevious = Boolean(data?.meta?.has_previous);
  const assayGroup = String(data?.assay_group || "").trim();
  const cosmicCancerGeneMap = data?.cosmic_cancer_gene_map || {};

  const columns: ColumnDef<any, any>[] = [
    createRowSelectionColumn<any>(),
    {
      id: "badges",
      header: "Info",
      meta: {
        exportValue: statusLabels,
        headerClassName: "w-[4.5rem] min-w-[4.5rem] max-w-[4.5rem]",
        cellClassName: "w-[4.5rem] min-w-[4.5rem] max-w-[4.5rem]",
      },
      accessorFn: (row) => statusLabels(row),
      enableSorting: false,
      size: 72,
      minSize: 72,
      maxSize: 72,
      cell: ({ row }) => (
        <StatusBadges
          finding={row.original}
          cosmicCancerGenes={matchedKnowledgebaseGenes(
            fusionGenes(row.original),
            cosmicCancerGeneMap,
          )}
        />
      ),
    },
    {
      id: "gene1",
      header: "Gene 1",
      accessorFn: (row) => fusionGenes(row)[0] || "-",
      cell: ({ row }) => {
        const genes = fusionGenes(row.original);
        const gene = genes[0];
        return gene ? (
          <Link
            to={tieredVariantSearchPath(gene, assayGroup)}
            className="type-table-value-emphasis link-text"
          >
            {gene}
          </Link>
        ) : (
          <span className="type-table-value">-</span>
        );
      },
    },
    {
      id: "gene2",
      header: "Gene 2",
      accessorFn: (row) => fusionGenes(row)[1] || "-",
      cell: ({ row }) => {
        const genes = fusionGenes(row.original);
        const gene = genes[1];
        return gene ? (
          <Link
            to={tieredVariantSearchPath(gene, assayGroup)}
            className="type-table-value-emphasis link-text"
          >
            {gene}
          </Link>
        ) : (
          <span className="type-table-value">-</span>
        );
      },
    },
    {
      id: "effect",
      header: "Effect",
      accessorFn: (row) => selectedFusionCall(row)?.effect || row.frame || "Unknown",
      cell: ({ row }) => (
        <FusionEffectBadge
          effect={selectedFusionCall(row.original)?.effect || row.original.frame}
        />
      ),
    },
    {
      id: "spanpairs",
      header: "SP",
      accessorFn: (row) => selectedFusionCall(row)?.spanpairs || row.supporting_reads?.span || 0,
      cell: ({ row }) => (
        <span className="type-table-value">
          {selectedFusionCall(row.original)?.spanpairs ||
            row.original.supporting_reads?.span ||
            "-"}
        </span>
      ),
    },
    {
      id: "unique_spanpairs",
      header: "Unique SR",
      accessorFn: (row) => selectedFusionCall(row)?.spanreads || row.supporting_reads?.split || 0,
      cell: ({ row }) => (
        <span className="type-table-value">
          {selectedFusionCall(row.original)?.spanreads ||
            row.original.supporting_reads?.split ||
            "-"}
        </span>
      ),
    },
    {
      id: "fusion_points",
      header: "Fusion points",
      accessorFn: (row) => {
        const call = selectedFusionCall(row);
        return (
          [call?.breakpoint1, call?.breakpoint2].filter(Boolean).join(", ") ||
          row.breakpoints?.join(", ") ||
          "-"
        );
      },
      cell: ({ row }) => {
        const call = selectedFusionCall(row.original);
        const bps = [call?.breakpoint1, call?.breakpoint2].filter(Boolean);
        const breakpoints = bps.length ? bps : row.original.breakpoints || [];
        return (
          <div className="type-table-value flex flex-col gap-0.5 leading-tight">
            {breakpoints.map((bp: string, i: number) => (
              <span key={i} className="bg-muted/50 px-1.5 py-0.5 rounded w-max">
                {bp}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      id: "tier",
      accessorFn: tierValue,
      meta: {
        exportValue: (row: any) => (tierValue(row) === 999 ? "" : tierValue(row)),
        headerClassName: "w-14 min-w-14",
        cellClassName: "w-14 min-w-14",
      },
      header: "Tier",
      cell: ({ row }) => <TierBadge tier={tierValue(row.original)} />,
    },
    {
      id: "description",
      header: "Description",
      accessorFn: (row) => selectedFusionCall(row)?.desc || row.desc || "-",
      cell: ({ row }) => (
        <FusionEvidenceBadges
          description={selectedFusionCall(row.original)?.desc || row.original.desc}
          metadata={data?.fusion_annotation_metadata}
        />
      ),
    },
    {
      id: "callers",
      header: "Callers",
      accessorFn: fusionCallers,
      cell: ({ row }) => <FusionCallerBadges callers={fusionCallers(row.original)} />,
    },
    {
      id: "actions",
      header: "",
      meta: DETAIL_NAVIGATION_COLUMN_META,
      cell: ({ row }) => {
        return (
          <div className="flex items-center justify-center">
            <DetailNavigationButton
              to={`/samples/${sampleId}/fusion/${row.original._id}`}
              state={{ from: `${location.pathname}${location.search}` }}
              label="View fusion details"
              description="Open the complete fusion record, evidence, comments, and classification controls."
            />
          </div>
        );
      },
    },
  ];

  return (
    <AnalysisTableCard header={header} filterPanel={filterPanel} className="p-2">
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
        renderToolbar={
          canManage
            ? (table) => (
                <BulkActionDropdown
                  selectedCount={Object.keys(table.getState().rowSelection).length}
                  actions={fusionBulkActions}
                  isPending={bulkAction.isPending}
                  onAction={(action) =>
                    bulkAction.mutateAsync({
                      action,
                      resourceIds: table
                        .getSelectedRowModel()
                        .rows.map((row: any) => String(row.original._id)),
                    })
                  }
                />
              )
            : undefined
        }
        renderExportButton={() => (
          <ServerCsvButton
            endpoint={`/samples/${sampleId}/fusions/exports/context`}
            fallbackFilename={`${sampleId}.filtered.fusions.csv`}
            label="Export to CSV"
          />
        )}
      />
    </AnalysisTableCard>
  );
}
