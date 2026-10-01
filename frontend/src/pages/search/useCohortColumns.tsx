import { ExpandableText } from "@/components/detail/ExpandableText";
import { TableBadge } from "@/components/ui/table-badge";
import { nomenclatureLabel } from "@/lib/application-constants";
import { valueBadgeClass } from "@/lib/badge-colors";
import { sampleDetailPath } from "@/lib/sample-routing";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { humanSex, percent } from "./cohort-formatters";
import { CurrentAndPriorTiers, PrevalenceBar } from "./cohort-presentation";
import { type AssayCohortRow, type CohortSample, type RecurrentFinding } from "./cohort-types";

export function useCohortColumns() {
  const assayColumns = useMemo<ColumnDef<AssayCohortRow>[]>(
    () => [
      {
        accessorKey: "display_name",
        header: "Assay",
        cell: ({ row }) => <span className="font-medium">{row.original.display_name}</span>,
      },
      {
        accessorKey: "asp_group",
        header: "Group",
        cell: ({ row }) => row.original.asp_group || "-",
      },
      { accessorKey: "finding_samples", header: "Findings" },
      { accessorKey: "profiled_samples", header: "Profiled" },
      {
        accessorKey: "prevalence_percent",
        header: "Prevalence",
        cell: ({ row }) => (
          <div className="grid min-w-40 grid-cols-[1fr_4.5rem] items-center gap-2">
            <PrevalenceBar value={row.original.prevalence_percent} />
            <span className="text-right font-medium">
              {percent(row.original.prevalence_percent)}
            </span>
          </div>
        ),
      },
    ],
    [],
  );
  const recurrentColumns = useMemo<ColumnDef<RecurrentFinding>[]>(
    () => [
      {
        accessorKey: "analysis_type",
        header: "Type",
        cell: ({ row }) => (
          <TableBadge className={valueBadgeClass(row.original.analysis_type)}>
            {row.original.analysis_type}
          </TableBadge>
        ),
      },
      { id: "genes", header: "Gene(s)", accessorFn: (row) => row.genes.join(" / ") || "-" },
      {
        accessorKey: "identity",
        header: "Finding",
        cell: ({ row }) => <ExpandableText text={row.original.identity} maxLength={32} />,
      },
      {
        id: "nomenclature",
        header: "Nomenclature",
        accessorFn: (row) => nomenclatureLabel(row.nomenclature),
      },
      {
        accessorKey: "hgvsp",
        header: "HGVSp",
        cell: ({ row }) => <ExpandableText text={row.original.hgvsp || "-"} maxLength={28} />,
      },
      {
        accessorKey: "hgvsc",
        header: "HGVSc",
        cell: ({ row }) => <ExpandableText text={row.original.hgvsc || "-"} maxLength={30} />,
      },
      {
        accessorKey: "genomic",
        header: "Genomic",
        cell: ({ row }) => <ExpandableText text={row.original.genomic || "-"} maxLength={30} />,
      },
      {
        accessorKey: "transcript",
        header: "Transcript",
        cell: ({ row }) => row.original.transcript || "-",
      },
      {
        id: "tiers",
        header: "Current / prior tiers",
        accessorFn: (row) => [...row.latest_tiers, ...row.historical_tiers].join(", "),
        cell: ({ row }) => (
          <CurrentAndPriorTiers
            current={row.original.latest_tiers}
            prior={row.original.historical_tiers}
          />
        ),
      },
      { accessorKey: "sample_count", header: "Samples" },
      { accessorKey: "observation_count", header: "Observations" },
    ],
    [],
  );
  const sampleColumns = useMemo<ColumnDef<CohortSample>[]>(
    () => [
      {
        accessorKey: "sample_name",
        header: "Sample",
        cell: ({ row }) => (
          <Link
            className="font-medium text-link hover:underline"
            to={sampleDetailPath(row.original, row.original.sample_name)}
          >
            {row.original.sample_name}
          </Link>
        ),
      },
      { accessorKey: "asp_id", header: "Assay", cell: ({ row }) => row.original.asp_id || "-" },
      {
        accessorKey: "subpanel_id",
        header: "Subpanel",
        cell: ({ row }) => row.original.subpanel_id || "-",
      },
      {
        accessorKey: "environment",
        header: "Environment",
        cell: ({ row }) => {
          const environment = row.original.environment || "";
          return environment ? (
            <TableBadge
              className={`${valueBadgeClass(environment)} uppercase`}
              title={environment}
              aria-label={environment}
            >
              {environment.charAt(0)}
            </TableBadge>
          ) : (
            "-"
          );
        },
      },
      {
        id: "sex",
        header: "Sex",
        accessorFn: (row) => (row.sex ? humanSex(row.sex) : "Unknown"),
      },
      {
        id: "findings",
        header: "Reported findings",
        accessorFn: (row) => row.finding_details.map((finding) => finding.identity).join(" "),
        cell: ({ row }) => (
          <div className="min-w-72 space-y-2">
            {row.original.finding_details.map((finding) => (
              <div
                key={`${finding.analysis_type}:${finding.identity}`}
                className="flex flex-wrap items-center gap-1.5"
              >
                <TableBadge className={valueBadgeClass(finding.analysis_type)}>
                  {finding.analysis_type}
                </TableBadge>
                <ExpandableText
                  text={finding.identity}
                  maxLength={32}
                  className="font-medium text-foreground"
                />
                <CurrentAndPriorTiers
                  current={[finding.latest_tier]}
                  prior={finding.tiers.filter((tier) => tier !== finding.latest_tier)}
                />
              </div>
            ))}
          </div>
        ),
      },
    ],
    [],
  );

  return { assayColumns, recurrentColumns, sampleColumns };
}
