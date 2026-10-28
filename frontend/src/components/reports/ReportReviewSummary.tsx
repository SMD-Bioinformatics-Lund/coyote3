import { ChevronDown } from "lucide-react"
import { ReportFindings } from "./ReportFindings"
import { REPORT_SNAPSHOT_SECTIONS, isCompactReportBiomarker, reportSnapshotAnalysisType,
  type ReportSnapshotRow, type ReportType } from "./report-snapshot"

export function ReportReviewSummary({ reportType, snapshotRows, snapshotCount, includeSnapshot,
  onIncludeSnapshotChange, evaluation }: {
  reportType: ReportType
  snapshotRows: ReportSnapshotRow[]
  snapshotCount: number
  includeSnapshot: boolean
  onIncludeSnapshotChange: (included: boolean) => void
  evaluation: unknown
}) {
  const visibleSnapshotSections = REPORT_SNAPSHOT_SECTIONS
    .map((section) => ({
      ...section,
      rows: snapshotRows.filter((row) => reportSnapshotAnalysisType(row, reportType) === section.type),
    }))
    .filter((section) => section.rows.length > 0)
  const ruleSource = evaluation && typeof evaluation === "object" && "source" in evaluation
    && evaluation.source !== null && typeof evaluation.source === "object"
    ? evaluation.source as Record<string, unknown> : undefined
  return (
    <aside className="report-inspector" aria-label="Report review">
      <div className="report-inspector-heading">
        <div className="min-w-0">
          <h3 className="type-card-title text-foreground">Review summary</h3>
          <p className="mt-1 type-body-sm text-muted-foreground">
            {includeSnapshot
              ? `${snapshotCount} included ${snapshotCount === 1 ? "finding" : "findings"}`
              : "Finding snapshot off"}
          </p>
        </div>
        <label className="report-snapshot-toggle type-body-sm">
          <span>Include findings</span>
          <input type="checkbox" role="switch" aria-label="Include finding snapshot"
            checked={includeSnapshot} onChange={(event) => onIncludeSnapshotChange(event.target.checked)} />
        </label>
      </div>
      <div className="report-inspector-body">
        <div className="report-findings-list">
          {includeSnapshot && visibleSnapshotSections.length > 0 ? visibleSnapshotSections.map((section) => isCompactReportBiomarker(section.type) ? (
            <section key={section.type} aria-label={`${section.label} included findings`} className="report-finding-section report-biomarker-section">
              <h4 className="font-semibold type-body-sm">{section.label}</h4>
              <div className="pt-3">
                <ReportFindings analysisType={section.type} columns={section.columns} rows={section.rows} />
              </div>
            </section>
          ) : (
            <details key={section.type} open className="report-finding-section report-record-section group/report-section">
              <summary className="interaction-transition flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
                <span className="font-semibold type-body-sm text-foreground">{section.label}</span>
                <span className="ml-auto rounded-md border border-border bg-muted/50 px-1.5 py-0.5 type-meta text-muted-foreground">{section.rows.length}</span>
                <ChevronDown className="size-3.5 text-muted-foreground transition-transform group-open/report-section:rotate-180" aria-hidden="true" />
              </summary>
              <ReportFindings
                analysisType={section.type}
                columns={section.columns}
                rows={section.rows}
              />
            </details>
          )) : (
            <div className="py-4 type-body-sm text-muted-foreground">
              {includeSnapshot ? "No reportable findings are included in this snapshot." : "The finding snapshot is turned off for this preview."}
            </div>
          )}
        </div>
        <p className="report-save-note type-meta text-muted-foreground">This preview is temporary. Save report to preserve the document and its findings.</p>
        {ruleSource && <details className="report-rule-details type-meta text-muted-foreground">
          <summary className="w-fit cursor-pointer rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Report rule details</summary>
          <p className="mt-2 break-words">
            {String(ruleSource.rule_set_id ?? "")} · v{String(ruleSource.content_version ?? "")} · {String(ruleSource.language ?? "")}
            {ruleSource.resolved_diagnosis_id === "base" && ruleSource.requested_diagnosis_id !== "base" ? " · Assay Base scope" : " · Exact scope"}
          </p>
        </details>}
      </div>
    </aside>
  )
}
