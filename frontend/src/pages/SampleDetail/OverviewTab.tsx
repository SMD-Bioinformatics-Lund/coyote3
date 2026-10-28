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
import { AlertTriangle, ChartNoAxesCombined, Database, Dna, Layers, Network, UserRound, Workflow } from "lucide-react"
import { ConfigurationApplyButton, type ConfigurationApplication } from "./ConfigurationApplyButton"
import { Link } from "react-router-dom"
import { displayValue, fileItems, formatFileSize, formatPurityPercentage, overviewFilterGroups, reportItems } from "./overview-data"
import { StatusPill } from "./OverviewStatusPill"

export function OverviewTab({ sampleId, sample, context }: { sampleId: string; sample: any; context?: any }) {
  const queryClient = useQueryClient()
  const applyLatestAspc = useMutation({
    mutationFn: (request: ConfigurationApplication) => api.post(`/samples/${sampleId}/aspc/apply-latest`, request).then((response) => response.data),
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
  const omics = String(sample?.asp_category || "").toLowerCase()
  const reports = reportItems(sample)
  const filterGroups = overviewFilterGroups(sample, context)
  const resolution = context?.assay_config?.aspc_resolution
  const databaseVersions = Object.entries(sample?.database_versions || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
  const metadataGroups = [
    { title: "Analysis", icon: Dna, fields: [
      { label: "Type", value: sample?.asp_category || sample?.asp_family ? <>
        {sample?.asp_category && <StatusPill tone="blue">{String(sample.asp_category).toUpperCase()}</StatusPill>}
        {sample?.asp_family && <StatusPill tone="blue">{sample.asp_family}</StatusPill>}
      </> : null },
      { label: "Sequencing", value: sample?.platform || sample?.read_mode ? <>
        {sample?.platform && <StatusPill tone="green">{sample.platform}</StatusPill>}
        {sample?.read_mode && <StatusPill tone="green">{sample.read_mode}</StatusPill>}
      </> : null },
      { label: "Reference", value: sample?.genome_build ? <StatusPill>{`GRCh${sample.genome_build}`}</StatusPill> : null },
      { label: "Environment", value: sample?.environment ? <StatusPill tone="yellow">{sample.environment}</StatusPill> : null },
    ] },
    { title: "Workflow", icon: Workflow, fields: [
      { label: "Assay", value: sample?.asp_id ? <StatusPill tone="blue">{sample.asp_id}</StatusPill> : null },
      { label: "Configuration", value: context?.assay_config?.aspc_id ? <StatusPill tone="blue">{context.assay_config.aspc_id}{context.assay_config.version ? ` v${context.assay_config.version}` : ""}</StatusPill> : null },
      { label: "Pipeline", value: sample?.pipeline ? <StatusPill tone="blue">{sample.pipeline}{sample.pipeline_version ? ` v${sample.pipeline_version}` : ""}</StatusPill> : null },
      { label: "Reporting", value: sampleReported(sample) ? <StatusPill tone="blue">Reported</StatusPill> : null },
    ] },
    { title: "Record history", icon: UserRound, fields: [
      { label: "Created by", value: sample?.created_by || "Unknown" },
      { label: "Updated by", value: sample?.updated_by || "Unknown" },
    ] },
  ]

  return (
    <div className="space-y-3">
      {resolution?.used_base_configuration && (
        <section className="glass-card flex items-start gap-2 border-warn/35 bg-card/95 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <div className="min-w-0">
            <strong className="text-warn">Base configuration in use.</strong>{" "}
            <span className="text-muted-foreground">
              {resolution.warning || "No diagnosis-specific assay configuration is active."}{" "}
              Requested diagnosis: <strong className="text-foreground">{resolution.requested_diagnosis_id}</strong>.
            </span>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 items-stretch gap-3 xl:grid-cols-5">
        <SettingsCard title="Sample Meta" tone="border-t-yellow-400" className="sample-meta-card xl:col-span-1">
          {metadataGroups.filter((group) => group.fields.some((field) => field.value !== null))
            .map(({ title, icon: Icon, fields }) => <section key={title} className="sample-meta-group" aria-label={title}>
              <h3 className="sample-meta-group-title type-label"><Icon className="size-3.5" aria-hidden="true" />{title}</h3>
              <dl className="sample-meta-fields">
                {fields.filter((field) => field.value !== null).map((field) => <div key={field.label}>
                  <dt className="type-meta">{field.label}</dt>
                  <dd className="type-body-sm">{field.value}</dd>
                </div>)}
              </dl>
            </section>)}
          <section className="sample-meta-group" aria-label="Database versions">
            <h3 className="sample-meta-group-title type-label"><Database className="size-3.5" aria-hidden="true" />Database versions</h3>
            {databaseVersions.length ? <dl className="sample-meta-fields">
              {databaseVersions.map(([key, value]) => <div key={key}>
                <dt className="type-meta">{key === "vep" ? "VEP" : key}</dt>
                <dd className="type-body-sm">{key === "vep" ? <VepVersionBadge version={value} /> :
                  <StatusPill>{displayValue(value)}</StatusPill>}</dd>
              </div>)}
            </dl> : <p className="type-meta text-muted-foreground">Not recorded</p>}
          </section>
          {context?.aspc_update?.available && (
            <div className="mt-3 rounded-lg border border-primary/25 bg-primary/5 p-2">
              <p className="text-xs font-semibold">Newer assay configuration available: {context.aspc_update.latest_aspc_id}{context.aspc_update.latest_version ? ` v${context.aspc_update.latest_version}` : ""}</p>
              <ConfigurationApplyButton sampleId={sampleId} pending={applyLatestAspc.isPending} apply={applyLatestAspc.mutateAsync} />
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

        <SettingsCard title={`Files & QC (${sample?.asp_category || "-"})`} tone="border-t-orange-800" className="xl:col-span-2">
          <div className="space-y-2">
            {files.length ? files.map((file: any, index: number) => (
              <div key={file.key || file.path || index} className="content-item flex items-start justify-between gap-3 px-3 py-2">
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
                <div key={String(reportId)} className="content-item p-3">
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
                  <div key={scope} className="content-item p-2">
                    <p className="type-label text-muted-foreground">{scope}</p>
                    <p className="type-body-sm mt-0.5 text-foreground">{entry?.label || "Ad Hoc"}</p>
                    <p className="type-meta text-muted-foreground">{(entry?.genes || []).length} gene(s)</p>
                  </div>
                )) : <p className="type-body-sm text-muted-foreground">No ad-hoc genes configured.</p>}
              </div>
            </section>
          </div>
        </SettingsCard>

        <SettingsCard title="Configured Filters" tone="border-t-blue-400" className="col-span-full">
          <div className="configured-filter-grid">
            {filterGroups.length ? filterGroups.map((group) => {
              const Icon = group.key === "cnv" ? Layers
                : group.key === "coverage" ? ChartNoAxesCombined
                : group.key.includes("snv") ? Dna : Network
              return <section key={group.key} aria-labelledby={`filter-group-${group.key}`}
                data-fact-columns={group.rows.filter(([, value]) => !Array.isArray(value)).length > 4 ? 3 : 2}
                className="content-item configured-filter-card">
                <header className="configured-filter-heading">
                  <span className="configured-filter-icon"><Icon className="size-4" aria-hidden="true" /></span>
                  <h3 id={`filter-group-${group.key}`} className="type-card-title text-foreground">{group.label}</h3>
                </header>
                <dl className="configured-filter-fields">
                  {group.rows.map(([label, rowValue]) => (
                    <div key={label} className={`configured-filter-field ${Array.isArray(rowValue) ? "is-list" : ""}`}>
                      <dt className="type-meta text-muted-foreground">{label}</dt>
                      <dd className="type-body-sm text-foreground">
                        {Array.isArray(rowValue) && rowValue.length > 0
                          ? <ul className="configured-filter-tokens" aria-label={label}>
                            {rowValue.map((value, index) => <li key={index} className="configured-filter-token">{String(value ?? "")}</li>)}
                          </ul>
                          : <span className="type-numeric font-semibold">{displayValue(rowValue)}</span>}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            }) : <p className="type-body-sm text-muted-foreground">No configurable filters apply to the enabled analyses for this sample.</p>}
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
