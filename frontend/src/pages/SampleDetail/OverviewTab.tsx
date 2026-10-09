import { TimeDisplay } from "@/components/ui/time-display"
import { VepVersionBadge } from "@/components/ui/vep-version-badge"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { apiPath } from "@/lib/runtime-paths"
import {
  sampleArtifactCountLabel,
  sampleArtifactPresentation,
  sampleArtifactStatus,
} from "@/lib/sample-artifact-ui"
import { sampleFilterSection, sampleReported } from "@/lib/sample-shape"
import { SampleGeneSettings, SettingsCard } from "@/pages/SampleDetail/SampleGeneSettings"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Link } from "react-router-dom"
import { AnalysisStatusStrip } from "./AnalysisStatusStrip"
import { displayValue, fileItems, formatFileSize, formatPurityPercentage, overviewFilterGroups, reportItems } from "./overview-data"
import { StatusPill } from "./OverviewStatusPill"

export function OverviewTab({ sampleId, sample, context }: { sampleId: string; sample: any; context?: any }) {
  const queryClient = useQueryClient()
  const applyLatestAspc = useMutation({
    mutationFn: () => api.post(`/samples/${sampleId}/aspc/apply-latest`, {}).then((response) => response.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sample", sampleId] })
      queryClient.invalidateQueries({ queryKey: ["samples"] })
      notifySuccess("Latest assay configuration applied", "The sample now uses the latest assay configuration.", "Assay configuration", { type: "sample", id: sampleId, name: sample?.name || sampleId })
    },
    onError: (error) => notifyActionError("Unable to apply latest assay configuration", error, "Assay configuration", { type: "sample", id: sampleId, name: sample?.name || sampleId }),
  })
  const verificationSample = context?.verification_sample_used || sample?.verification_sample_used
  const files = fileItems(context)
  const snvFilters = sampleFilterSection(sample, "snv")
  const cnvFilters = sampleFilterSection(sample, "cnv")
  const fusionFilters = sampleFilterSection(sample, "fusion")
  const translocationFilters = sampleFilterSection(sample, "translocation")
  const adhoc = {
    ...(snvFilters?.adhoc_genes ? { snv: snvFilters.adhoc_genes } : {}),
    ...(cnvFilters?.adhoc_genes ? { cnv: cnvFilters.adhoc_genes } : {}),
    ...(fusionFilters?.adhoc_genes ? { fusion: fusionFilters.adhoc_genes } : {}),
  }
  const omics = String(sample?.omics_layer || "").toLowerCase()
  const reports = reportItems(sample)
  const filterGroups = overviewFilterGroups(sample, context)

  return (
    <div className="space-y-3">
      <AnalysisStatusStrip sample={sample} context={context} />

      {sample?.aspc_resolution?.used_base_configuration && (
        <section className="glass-card flex items-start gap-2 border-warn/35 bg-card/95 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <div className="min-w-0">
            <strong className="text-warn">Base configuration in use.</strong>{" "}
            <span className="text-muted-foreground">
              {sample.aspc_resolution.warning || "No subpanel-specific assay configuration is active."}{" "}
              Requested subpanel: <strong className="text-foreground">{sample.aspc_resolution.requested_subpanel_id}</strong>.
            </span>
          </div>
        </section>
      )}

      <div className="grid gap-3 xl:grid-cols-5">
        <SettingsCard title="Sample Meta" tone="border-t-yellow-400" className="xl:col-span-1">
          <div className="flex flex-wrap gap-2">
            {sample?.omics_layer && <StatusPill tone="blue">{String(sample.omics_layer).toUpperCase()}</StatusPill>}
            {sample?.platform && <StatusPill tone="green">{sample.platform}</StatusPill>}
            {sample?.read_mode && <StatusPill tone="green">{sample.read_mode}</StatusPill>}
            {sample?.sequencing_scope && <StatusPill tone="blue">{sample.sequencing_scope}</StatusPill>}
            {sample?.genome_build && <StatusPill>{`GRCh${sample.genome_build}`}</StatusPill>}
            {sample?.environment && <StatusPill tone="yellow">{sample.environment}</StatusPill>}
            {sample?.asp_id && <StatusPill tone="blue">Assay: {sample.asp_id}</StatusPill>}
            {sample?.current_aspc_key && <StatusPill tone="blue">Configuration: {sample.current_aspc_key}{sample.current_aspc_version ? ` v${sample.current_aspc_version}` : ""}</StatusPill>}
            {sample?.pipeline && <StatusPill tone="blue">{sample.pipeline}{sample.pipeline_version ? ` v${sample.pipeline_version}` : ""}</StatusPill>}
            {sampleReported(sample) && <StatusPill tone="blue">Reported</StatusPill>}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Database versions</span>
            {Object.entries(sample?.database_versions || {}).filter(([, value]) => value !== null && value !== undefined && value !== "").map(([key, value]) => (
              key === "vep" ? <VepVersionBadge key={key} version={value} /> :
                <StatusPill key={key}>{key}: {displayValue(value)}</StatusPill>
            ))}
            {!Object.keys(sample?.database_versions || {}).length && <span className="text-sm text-muted-foreground">Not recorded</span>}
          </div>
          {context?.aspc_update?.available && (
            <div className="mt-3 rounded-lg border border-primary/25 bg-primary/5 p-2">
              <p className="text-xs font-semibold">Newer assay configuration available: {context.aspc_update.latest_aspc_id}{context.aspc_update.latest_version ? ` v${context.aspc_update.latest_version}` : ""}</p>
              <button
                type="button"
                disabled={applyLatestAspc.isPending}
                onClick={() => {
                  if (window.confirm("Apply the latest assay configuration? This replaces this sample's saved filters and analysis configuration.")) applyLatestAspc.mutate()
                }}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-primary px-2 py-1 text-xs font-semibold text-primary-foreground disabled:opacity-60"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {applyLatestAspc.isPending ? "Applying..." : "Apply latest configuration"}
              </button>
            </div>
          )}
        </SettingsCard>

        <SettingsCard title="Case and Control" tone="border-t-orange-400" className="xl:col-span-2">
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="type-table-cell w-full min-w-[38rem] border-separate border-spacing-0">
              <thead>
                <tr className="type-table-header bg-muted/65 text-left">
                  <th className="w-28 px-3 py-2 border-r-2 border-border">Field</th>
                  <th className="bg-pass/8 px-3 py-2 text-pass border-r-2 border-border">Case</th>
                  <th className="bg-tier3/8 px-3 py-2 text-tier3">Control</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["ID", sample?.case?.id || sample?.case_id, sample?.control?.id || sample?.control_id],
                  ["Clarity ID", sample?.case?.clarity_id, sample?.control?.clarity_id],
                  ["Pool ID", sample?.case?.clarity_pool_id, sample?.control?.clarity_pool_id],
                  ["Sequencing run", sample?.case?.sequencing_run, sample?.control?.sequencing_run],
                  ["Reads", sample?.case?.reads, sample?.control?.reads],
                  ["BAM", sample?.case?.bam, sample?.control?.bam],
                  ["FFPE", sample?.case?.ffpe ? "Yes" : "No", sample?.control?.ffpe ? "Yes" : "No"],
                  ["Purity", formatPurityPercentage(sample?.case?.purity), formatPurityPercentage(sample?.control?.purity)],
                ].map(([label, caseValue, controlValue]) => (
                  <tr key={String(label)} className="border-t border-border/40">
                    <th scope="row" className="border-t border-r border-border text-sm bg-muted/35 px-3 py-1 text-left font-semibold capitalize">{label}</th>
                    <td className="border-t border-r border-border bg-pass/5 px-3 py-1 text-sm font-normal text-foreground">{displayValue(caseValue)}</td>
                    <td className="border-t border-border bg-tier3/5 px-3 py-1 text-sm font-normal text-foreground">{sample?.paired ? displayValue(controlValue) : "Not paired"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SettingsCard>

        <SettingsCard title={`Files & QC (${sample?.omics_layer || "-"})`} tone="border-t-orange-800" className="xl:col-span-2">
          <div className="space-y-2">
            {files.length ? files.map((file: any, index: number) => (
              <div key={file.key || file.path || index} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-background/70 px-3 py-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">{sampleArtifactPresentation(file.analysis_type, file.key).label}</span>
                    <StatusPill tone={file.required ? "blue" : "muted"}>{file.required ? "Required" : "Optional"}</StatusPill>
                    {formatFileSize(file.size_bytes) && (
                      <StatusPill tone="muted">{formatFileSize(file.size_bytes)}</StatusPill>
                    )}
                    {sampleArtifactCountLabel(file.analysis_type, file.data_count) && (
                      <StatusPill tone="green">{sampleArtifactCountLabel(file.analysis_type, file.data_count)}</StatusPill>
                    )}
                  </div>
                  <p className={`mt-0.5 break-all type-meta ${file.path && file.exists === false ? "text-fail" : "text-muted-foreground"}`}>
                    {file.path || sampleArtifactPresentation(file.analysis_type, file.key).missingMessage}
                  </p>
                  {file.checksum && (
                    <p className="mt-0.5 truncate type-label text-muted-foreground">
                      checksum {file.checksum}
                    </p>
                  )}
                </div>
                <StatusPill tone={sampleArtifactStatus(file.availability).tone}>
                  {sampleArtifactStatus(file.availability).label}
                </StatusPill>
              </div>
            )) : <p className="text-sm text-muted-foreground">No assay-configured files for this sample.</p>}
          </div>
        </SettingsCard>
      </div>

      {reports.length > 0 && (
        <SettingsCard title="Saved Reports" tone="border-t-tier3">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {reports.map((report: any, index: number) => {
              const reportId = report?._id || report?.id || report?.report_id || report?.report_num || index
              const label = report?.report_name || report?.file || report?.report_id || `Report ${index + 1}`
              return (
                <div key={String(reportId)} className="rounded-xl border border-border bg-background/70 p-3">
                  <p className="break-all text-sm font-semibold">{label}</p>
                  <TimeDisplay
                    value={report?.created_at || report?.time_created || report?.date}
                    mode="full"
                    className="mt-1 text-xs text-muted-foreground"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link to={`/samples/${sample?.name || sampleId}/reports/${reportId}`} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground">
                      View
                    </Link>
                    <a href={apiPath(`/samples/${sample?.name || sampleId}/reports/${reportId}/download`)} className="rounded-lg border border-border px-3 py-1.5 text-xs font-bold hover:bg-muted">
                      Download
                    </a>
                  </div>
                </div>
              )
            })}
          </div>
        </SettingsCard>
      )}

      <div className="grid gap-3 xl:grid-cols-4">
        <SampleGeneSettings sampleId={sampleId} sample={sample} />

        <SettingsCard title="Gene Filters" tone="border-t-slate-400" className="xl:col-span-2">
          <div className="divide-y divide-border/60">
            {omics === "dna" && (
              <section className="py-3 first:pt-0">
                <h3 className="type-label text-pass">Selected SNV gene lists</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(snvFilters.snvlists || []).length ? snvFilters.snvlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No gene lists selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "dna" && (
              <section className="py-3">
                <h3 className="type-label text-warn">Selected CNV gene lists</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(cnvFilters.cnvlists || []).length ? cnvFilters.cnvlists.map((name: string) => <StatusPill key={name} tone="yellow">{name}</StatusPill>) : <p className="text-muted-foreground">No CNV gene lists selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "rna" && (
              <section className="py-3 first:pt-0">
                <h3 className="type-label text-tier4">Selected Fusion Lists</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(fusionFilters.fusionlists || []).length ? fusionFilters.fusionlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No fusion lists selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "dna" && (
              <section className="py-3">
                <h3 className="type-label text-tier3">Selected DNA Fusion / Translocation gene lists</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(translocationFilters.fusionlists || []).length ? translocationFilters.fusionlists.map((name: string) => <StatusPill key={name} tone="blue">{name}</StatusPill>) : <p className="text-muted-foreground">No DNA fusion or translocation gene lists selected for this sample.</p>}
                </div>
              </section>
            )}
            <section className="py-3 last:pb-0">
              <h3 className="type-label text-tier3">Sample Ad-Hoc Genes</h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {Object.keys(adhoc).length ? Object.entries(adhoc).map(([scope, entry]: [string, any]) => (
                  <div key={scope} className="rounded-xl border border-border bg-background/70 p-2">
                    <p className="type-label text-muted-foreground">{scope}</p>
                    <p className="type-body-sm mt-0.5 text-foreground">{entry?.label || "Ad Hoc"}</p>
                    <p className="type-meta text-muted-foreground">{(entry?.genes || []).length} gene(s)</p>
                  </div>
                )) : <p className="type-body-sm text-muted-foreground">No ad-hoc genes configured.</p>}
              </div>
            </section>
          </div>
        </SettingsCard>

        <SettingsCard title="Configured Filters" tone="border-t-blue-400" className="col-span-4">
          <div className="space-y-3">
            {filterGroups.length ? filterGroups.map((group) => (
              <section key={group.key} aria-labelledby={`filter-group-${group.key}`} className="rounded-xl border border-border bg-background/55 p-2.5">
                <h3 id={`filter-group-${group.key}`} className="type-label mb-2 text-foreground">{group.label}</h3>
                <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {group.rows.map(([label, rowValue]) => (
                    <div key={label} className="rounded-lg bg-card px-2.5 py-2 shadow-sm">
                      <dt className="type-meta text-muted-foreground">{label}</dt>
                      <dd className="type-body-sm mt-0.5 break-words text-foreground">{displayValue(rowValue)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )) : <p className="text-sm text-muted-foreground">No configurable filters apply to the enabled analyses for this sample.</p>}
          </div>
        </SettingsCard>
      </div>

      {verificationSample && (
        <section className="paper-inset rounded-xl px-3 py-2">
          <h2 className="text-base font-semibold uppercase tracking-wide text-foreground">Verification Sample</h2>
          <p className="type-body-sm mt-2 font-semibold text-warn">
            Verification sample used: {verificationSample}
          </p>
        </section>
      )}
    </div>
  )
}
