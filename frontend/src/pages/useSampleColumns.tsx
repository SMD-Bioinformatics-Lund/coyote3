import { type CsvExportColumn } from "@/components/data-table/DataTable"
import { TableBadge } from "@/components/ui/table-badge"
import { TimeDisplay } from "@/components/ui/time-display"
import { valueBadgeClass } from "@/lib/badge-colors"
import { fullDateTime } from "@/lib/detail-formatters"
import { FILE_ANALYSIS_LABELS } from "@/lib/sample-artifact-ui"
import { sampleDetailPath } from "@/lib/sample-routing"
import { sampleSubpanel } from "@/lib/sample-shape"
import type { ColumnDef } from "@tanstack/react-table"
import { FileText } from "lucide-react"
import { useMemo } from "react"
import { Link } from "react-router-dom"
import { SampleDataStatus } from "./sample-data-status"
import { BOOLEAN_ANALYSIS_LABELS, countBadges, DATA_EXPORT_LABELS, exportScalar, firstDefinedValue, sampleFindingTotal, STANDARD_DATA_EXPORT_COLUMNS } from "./sample-list-presentation"

export function useSampleColumns() {
  const columns = useMemo<ColumnDef<any, any>[]>(() => [
    {
      id: "sample",
      header: "Sample",
      accessorFn: (sample) => sample.name || sample.case_id || "",
      cell: ({ row }) => {
        const sample = row.original
        return (
          <Link to={sampleDetailPath(sample)} className="link-text flex items-center gap-2 font-semibold">
            <div className="rounded-lg bg-primary/10 p-1.5 text-primary shadow-sm transition-colors duration-100 group-hover:bg-primary/15">
              <FileText className="h-4 w-4" />
            </div>
            {sample.name || sample.case_id}
          </Link>
        )
      },
      meta: {
        exportValue: (sample: any) => sample.name || sample.case_id || "",
        cellClassName: "min-w-[180px]",
      },
    },
    {
      id: "case_id",
      header: "Case ID",
      accessorFn: (sample) => sample.case_id || sample.case?.id || "",
      cell: ({ row }) => <span className="font-semibold">{row.original.case_id || row.original.case?.id || "-"}</span>,
    },
    {
      id: "case_clarity",
      header: "Case Clarity",
      accessorFn: (sample) => sample.case?.clarity_id || "",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.case?.clarity_id || "-"}</span>,
    },
    {
      id: "control",
      header: "Control",
      accessorFn: (sample) => sample.control_id || sample.control?.id || "",
      cell: ({ row }) => <span className="font-semibold">{row.original.control_id || row.original.control?.id || "-"}</span>,
    },
    {
      id: "control_clarity",
      header: "Control Clarity",
      accessorFn: (sample) => sample.control?.clarity_id || "",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.control?.clarity_id || "-"}</span>,
    },
    {
      id: "environment",
      header: "Profile",
      accessorFn: (sample) => sample.environment || "",
      cell: ({ row }) => (
        <TableBadge className={`${valueBadgeClass(row.original.environment || "")} uppercase`}>
          {row.original.environment[0] || "-"}
        </TableBadge>
      ),
    },
    {
      id: "asp_id",
      header: "Assay",
      accessorFn: (sample) => sample.asp_id || "",
      cell: ({ row }) => <span className="font-normal">{row.original.asp_id || "-"}</span>,
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (sample) => sampleSubpanel(sample) || "",
      cell: ({ row }) => <span className="font-normal">{sampleSubpanel(row.original) || "-"}</span>,
    },
    {
      id: "pipeline",
      header: "Pipeline",
      accessorFn: (sample) =>
        [sample.pipeline, sample.pipeline_version].filter(Boolean).join(" "),
      cell: ({ row }) => {
        const { pipeline, pipeline_version: version } = row.original

        return (
          <span className="font-normal">
            {pipeline ? `${pipeline}${version ? ` (${version})` : ""}` : "-"}
          </span>
        )
      },
    },
    {
      id: "data",
      header: "Data",
      enableSorting: false,
      accessorFn: sampleFindingTotal,
      cell: ({ row }) => {
        const badges = countBadges(row.original)
        return (
          <SampleDataStatus segments={badges} />
        )
      },
      meta: {
        exportValue: (sample: any) => {
          const counts = sample?.data_counts || {}
          return [
            counts.snvs !== undefined ? `SNV ${counts.snvs}` : "",
            counts.cnvs !== undefined ? `CNV ${counts.cnvs}` : "",
            counts.fusions !== undefined ? `Fusion ${counts.fusions}` : "",
            (counts.transloc ?? counts.translocations) !== undefined ? `SV ${counts.transloc ?? counts.translocations}` : "",
            ...Object.entries(counts)
              .filter(([, value]) => value === true)
              .map(([key]) => BOOLEAN_ANALYSIS_LABELS[key] || key.replaceAll("_", " ")),
            ...(sample?.missing_expected_files || []).map((key: string) =>
              `${FILE_ANALYSIS_LABELS[key] || key} not available`),
          ].filter(Boolean).join("; ")
        },
        cellClassName: "min-w-[220px]",
      },
    },
    {
      id: "added",
      header: "Added",
      accessorFn: (sample) => sample.time_added ? new Date(sample.time_added).getTime() : 0,
      cell: ({ row }) => (
        <TimeDisplay value={row.original.time_added} className="font-normal" />
      ),
      meta: {
        exportValue: (sample: any) => fullDateTime(sample.time_added),
        cellClassName: "whitespace-nowrap",
      },
    },
    {
      id: "latest_reported",
      header: "Latest reported",
      accessorFn: (sample) => sample.latest_report_on ? new Date(sample.latest_report_on).getTime() : 0,
      cell: ({ row }) => (
        <TimeDisplay value={row.original.latest_report_on} className="font-normal" />
      ),
      meta: {
        exportValue: (sample: any) => sample.latest_report_on
          ? fullDateTime(sample.latest_report_on)
          : "",
        cellClassName: "whitespace-nowrap",
      },
    }
  ], [])
  return columns
}

export function useSampleExportColumns(liveSamples: SampleListRow[], reportedSamples: SampleListRow[]) {
  const sampleExportColumns = useMemo<CsvExportColumn<any>[]>(() => {
    const loadedSamples = [...liveSamples, ...reportedSamples]
    const knownDataKeys = new Set<string>(
      STANDARD_DATA_EXPORT_COLUMNS.flatMap(({ aliases }) => [...aliases]),
    )
    const extraDataKeys = [...new Set(
      loadedSamples.flatMap((sample: any) => Object.keys(sample?.data_counts || {})),
    )].filter((key) => !knownDataKeys.has(key)).sort()
    const biomarkerKeys = [...new Set(
      loadedSamples.flatMap((sample: any) => Object.keys(sample?.biomarker_values || {})),
    )].sort()

    return [
      { header: "Sample", value: (sample) => sample.name || sample.case_id || "" },
      { header: "Case ID", value: (sample) => sample.case_id || sample.case?.id || "" },
      { header: "Case Clarity", value: (sample) => sample.case?.clarity_id || "" },
      { header: "Control ID", value: (sample) => sample.control_id || sample.control?.id || "" },
      { header: "Control Clarity", value: (sample) => sample.control?.clarity_id || "" },
      { header: "Profile", value: (sample) => sample.environment || "" },
      { header: "Assay", value: (sample) => sample.asp_id || "" },
      { header: "Subpanel", value: (sample) => sampleSubpanel(sample) || "" },
      { header: "Pipeline", value: (sample) => sample.pipeline || "" },
      { header: "Pipeline version", value: (sample) => sample.pipeline_version ?? "" },
      { header: "Analysis status", value: (sample) => sample.ingest_status || "" },
      { header: "Report status", value: (sample) => sample.reported ? "Reported" : "Unreported" },
      ...STANDARD_DATA_EXPORT_COLUMNS.map(({ key, aliases }) => ({
        header: DATA_EXPORT_LABELS[key],
        value: (sample: any) => exportScalar(
          firstDefinedValue(sample?.data_counts || {}, aliases),
        ),
      })),
      ...extraDataKeys.map((key) => ({
        header: DATA_EXPORT_LABELS[key] || key.replaceAll("_", " "),
        value: (sample: any) => exportScalar(sample?.data_counts?.[key]),
      })),
      ...biomarkerKeys.map((key) => ({
        header: key,
        value: (sample: any) => exportScalar(sample?.biomarker_values?.[key]),
      })),
      { header: "Added", value: (sample) => fullDateTime(sample.time_added) },
      { header: "Latest reported", value: (sample) => sample.latest_report_on ? fullDateTime(sample.latest_report_on) : "" },
    ]
  }, [liveSamples, reportedSamples])

  return sampleExportColumns
}

type SampleListRow = {
  data_counts?: Record<string, unknown>
  biomarker_values?: Record<string, unknown>
}
