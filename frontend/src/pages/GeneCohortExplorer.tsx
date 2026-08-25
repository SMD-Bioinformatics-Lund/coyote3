import { FormEvent, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart3, Dna, Search, Users } from "lucide-react"
import { Link, useSearchParams } from "react-router-dom"

import { GeneCohortCharts } from "@/components/gene-cohort/GeneCohortCharts"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { TableBadge } from "@/components/ui/table-badge"
import { api } from "@/lib/api"
import { valueBadgeClass } from "@/lib/badge-colors"
import { sampleDetailPath } from "@/lib/sample-routing"
import { cn } from "@/lib/utils"

type CohortBreakdown = {
  profiled_samples: number
  finding_samples: number
  prevalence_percent: number | null
}

type GeneCohortPayload = {
  query: { resolved_symbol?: string; requested?: string }
  gene?: Record<string, unknown> | null
  summary: CohortBreakdown & {
    reported_observations: number
    unique_findings: number
  }
  denominator: {
    method: string
    report_scope: "latest" | "historical"
    ready_samples_considered: number
    samples_excluded_outside_gene_scope: number
    unrestricted_asp_scope_counts_as_profiled: boolean
    duplicate_report_observations_removed: number
  }
  tier_counts: Record<string, number>
  analysis_type_counts: Record<string, number>
  assays: Array<CohortBreakdown & { asp_id: string; display_name: string; asp_group?: string }>
  sex_distribution: Array<CohortBreakdown & { sex: string }>
  recurrent_findings: Array<{
    identity: string
    analysis_type: string
    nomenclature?: string
    genes: string[]
    gene?: string
    gene1?: string
    gene2?: string
    hgvsp?: string
    hgvsc?: string
    genomic?: string
    transcript?: string
    sample_count: number
    observation_count: number
    tiers: number[]
  }>
  samples: Array<{
    sample_name: string
    asp_id?: string
    subpanel_id?: string
    environment?: string
    sex?: string
    tiers: number[]
    findings: string[]
    finding_types: string[]
  }>
  truncated: boolean
}

const tierClasses: Record<string, string> = {
  "1": "bg-tier1 text-white",
  "2": "bg-tier2 text-white",
  "3": "bg-tier3 text-white",
  "4": "bg-tier4 text-white",
}

function percent(value: number | null) {
  return value == null ? "Not available" : `${value.toFixed(2)}%`
}

function humanSex(value: string) {
  if (value === "not_recorded") return "Not recorded"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function PrevalenceBar({ value }: { value: number | null }) {
  const width = Math.max(0, Math.min(100, value || 0))
  return (
    <div className="h-2 overflow-hidden rounded-full bg-muted" aria-label={`Prevalence ${percent(value)}`}>
      <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
    </div>
  )
}

function MetricCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="metric-card rounded-xl">
      <p className="type-label text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      <p className="type-caption mt-1 text-muted-foreground">{detail}</p>
    </div>
  )
}

export function GeneCohortExplorer() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedGene = (searchParams.get("gene") || "").trim().toUpperCase()
  const includeHistory = searchParams.get("history") === "1"
  const [geneInput, setGeneInput] = useState(requestedGene)

  const cohortQuery = useQuery<GeneCohortPayload>({
    queryKey: ["gene-cohort", requestedGene, includeHistory],
    queryFn: () => api.get(
      `/common/gene/${encodeURIComponent(requestedGene)}/cohort-summary${includeHistory ? "?include_history=true" : ""}`,
    ).then((response) => response.data),
    enabled: Boolean(requestedGene),
  })

  const gene = cohortQuery.data?.query?.resolved_symbol || requestedGene
  const hgncId = String(
    cohortQuery.data?.gene?.hgnc_id || cohortQuery.data?.gene?.HGNC_ID || ""
  )
  const recurrentRows = useMemo(
    () => cohortQuery.data?.recurrent_findings || [],
    [cohortQuery.data?.recurrent_findings],
  )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const normalized = geneInput.trim().toUpperCase()
    if (!normalized) return
    const nextParams = new URLSearchParams()
    nextParams.set("gene", normalized)
    if (includeHistory) nextParams.set("history", "1")
    setSearchParams(nextParams)
  }

  const setHistoryMode = (enabled: boolean) => {
    const nextParams = new URLSearchParams(searchParams)
    if (enabled) nextParams.set("history", "1")
    else nextParams.delete("history")
    setSearchParams(nextParams)
  }

  return (
    <PageShell
      eyebrow="Common"
      title="Gene Cohort Explorer"
      description="Review reported SNV, CNV, fusion, and translocation prevalence for one gene across samples visible to your account."
      actions={
        <div className="flex w-full flex-col items-end gap-2 md:w-auto">
          <form onSubmit={submit} className="flex w-full items-center gap-2 md:w-auto">
            <div className="relative min-w-64 flex-1 md:w-80">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Gene symbol or HGNC identifier"
                value={geneInput}
                onChange={(event) => setGeneInput(event.target.value)}
                placeholder="Gene symbol or HGNC ID"
                className="pl-9"
              />
            </div>
            <Button type="submit">Search</Button>
          </form>
          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-foreground">
            <input
              type="checkbox"
              checked={includeHistory}
              onChange={(event) => setHistoryMode(event.target.checked)}
              className="h-4 w-4 rounded border-border accent-primary"
            />
            Include historical reports
          </label>
        </div>
      }
    >
      {!requestedGene && (
        <section className="surface-panel p-6 text-center">
          <Dna className="mx-auto h-8 w-8 text-primary" />
          <h2 className="mt-3 text-lg font-semibold">Search for a gene</h2>
          <p className="type-body mx-auto mt-1 max-w-2xl text-muted-foreground">
            Enter an approved gene symbol, previous symbol, alias, or HGNC identifier to build an access-scoped cohort summary.
          </p>
        </section>
      )}

      {cohortQuery.isLoading && <AppLoader label="Loading gene cohort" />}
      {cohortQuery.error && (
        <section className="surface-panel border-destructive/40 p-5 text-destructive">
          {cohortQuery.error instanceof Error ? cohortQuery.error.message : "The gene cohort could not be loaded."}
        </section>
      )}

      {cohortQuery.data && (
        <div className="space-y-4">
          <section className="surface-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
              <div>
                <p className="type-page-eyebrow text-primary">Gene cohort</p>
                <h2 className="text-2xl font-semibold text-foreground">{gene}</h2>
                {hgncId && <p className="type-caption mt-1 text-muted-foreground">{hgncId}</p>}
              </div>
              <Link to={`/public/gene/${encodeURIComponent(gene)}/info`}>
                <Button variant="outline" size="sm">Gene information</Button>
              </Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Profiled samples"
                value={cohortQuery.data.summary.profiled_samples}
                detail={`${cohortQuery.data.denominator.ready_samples_considered} ready samples considered`}
              />
              <MetricCard
                label="Finding prevalence"
                value={percent(cohortQuery.data.summary.prevalence_percent)}
                detail={`${cohortQuery.data.summary.finding_samples} sample(s) with a reported finding`}
              />
              <MetricCard
                label="Reported observations"
                value={cohortQuery.data.summary.reported_observations}
                detail={includeHistory
                  ? "Distinct sample-finding pairs across report history"
                  : "Latest saved report per sample"}
              />
              <MetricCard
                label="Unique findings"
                value={cohortQuery.data.summary.unique_findings}
                detail="Distinct typed clinical finding identities"
              />
            </div>
          </section>

          <GeneCohortCharts
            gene={gene}
            includeHistory={includeHistory}
            assays={cohortQuery.data.assays}
            tierCounts={cohortQuery.data.tier_counts}
            analysisTypeCounts={cohortQuery.data.analysis_type_counts}
            sexDistribution={cohortQuery.data.sex_distribution}
            recurrentFindings={recurrentRows}
          />

          <section className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,0.7fr)]">
            <div className="surface-panel p-4">
              <div className="surface-panel-heading">
                <h2 className="text-base font-semibold">Assay prevalence</h2>
                <p className="type-caption text-muted-foreground">Finding samples divided by samples profiled for {gene} in each assay.</p>
              </div>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="px-3 py-2">Assay</th>
                      <th className="px-3 py-2">Group</th>
                      <th className="px-3 py-2 text-right">Findings</th>
                      <th className="px-3 py-2 text-right">Profiled</th>
                      <th className="min-w-40 px-3 py-2">Prevalence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cohortQuery.data.assays.map((row) => (
                      <tr key={row.asp_id} className="border-t border-border">
                        <td className="px-3 py-2 font-medium">{row.display_name}</td>
                        <td className="px-3 py-2 text-muted-foreground">{row.asp_group || "-"}</td>
                        <td className="px-3 py-2 text-right">{row.finding_samples}</td>
                        <td className="px-3 py-2 text-right">{row.profiled_samples}</td>
                        <td className="px-3 py-2">
                          <div className="grid grid-cols-[1fr_4.5rem] items-center gap-2">
                            <PrevalenceBar value={row.prevalence_percent} />
                            <span className="text-right font-medium">{percent(row.prevalence_percent)}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="surface-panel p-4">
              <div className="surface-panel-heading">
                <h2 className="text-base font-semibold">Tier distribution</h2>
                <p className="type-caption text-muted-foreground">
                  {includeHistory
                    ? "Reported observations across report history, counted once per sample and typed finding."
                    : "Reported observations in the latest sample reports."}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((tier) => (
                  <div key={tier} className="content-item flex items-center justify-between p-3">
                    <TableBadge className={cn("border-transparent", tierClasses[String(tier)])}>Tier {tier}</TableBadge>
                    <strong className="text-xl font-semibold">{cohortQuery.data.tier_counts[String(tier)] || 0}</strong>
                  </div>
                ))}
              </div>
              <div className="mt-4 border-t border-border pt-4">
                <h3 className="text-sm font-semibold">Sex distribution</h3>
                <div className="mt-2 space-y-3">
                  {cohortQuery.data.sex_distribution.length ? cohortQuery.data.sex_distribution.map((row) => (
                    <div key={row.sex}>
                      <div className="mb-1 flex justify-between gap-3 text-sm">
                        <span>{humanSex(row.sex)}</span>
                        <span className="text-muted-foreground">{row.finding_samples}/{row.profiled_samples} ({percent(row.prevalence_percent)})</span>
                      </div>
                      <PrevalenceBar value={row.prevalence_percent} />
                    </div>
                  )) : <p className="type-body text-muted-foreground">No sex information is available.</p>}
                </div>
              </div>
            </div>
          </section>

          <section className="surface-panel p-4">
            <div className="surface-panel-heading flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Recurrent findings</h2>
                <p className="type-caption text-muted-foreground">Typed clinical findings ordered by the number of affected samples.</p>
              </div>
            </div>
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-left text-sm">
                <thead><tr><th className="px-3 py-2">Type</th><th className="px-3 py-2">Gene(s)</th><th className="px-3 py-2">Finding</th><th className="px-3 py-2">Nomenclature</th><th className="px-3 py-2">HGVSp</th><th className="px-3 py-2">HGVSc</th><th className="px-3 py-2">Genomic</th><th className="px-3 py-2">Transcript</th><th className="px-3 py-2">Tiers</th><th className="px-3 py-2 text-right">Samples</th><th className="px-3 py-2 text-right">Observations</th></tr></thead>
                <tbody>
                  {recurrentRows.map((row) => (
                    <tr key={`${row.analysis_type}:${row.identity}:${row.genes.join("|")}`} className="border-t border-border">
                      <td className="px-3 py-2"><TableBadge className={valueBadgeClass(row.analysis_type)}>{row.analysis_type}</TableBadge></td>
                      <td className="px-3 py-2 font-medium">{row.genes.join(" / ") || "-"}</td>
                      <td className="px-3 py-2 font-medium">{row.identity}</td>
                      <td className="px-3 py-2">{row.nomenclature || "-"}</td>
                      <td className="px-3 py-2">{row.hgvsp || "-"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{row.hgvsc || "-"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{row.genomic || "-"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{row.transcript || "-"}</td>
                      <td className="px-3 py-2"><div className="flex gap-1">{row.tiers.map((tier) => <TableBadge key={tier} className={cn("border-transparent", tierClasses[String(tier)])}>{tier}</TableBadge>)}</div></td>
                      <td className="px-3 py-2 text-right font-medium">{row.sample_count}</td>
                      <td className="px-3 py-2 text-right">{row.observation_count}</td>
                    </tr>
                  ))}
                  {!recurrentRows.length && <tr><td colSpan={11} className="px-3 py-8 text-center text-muted-foreground">No reported findings were found.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="surface-panel p-4">
            <div className="surface-panel-heading flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              <div><h2 className="text-base font-semibold">Samples with reported findings</h2><p className="type-caption text-muted-foreground">Samples are linked to their clinical workspace.</p></div>
            </div>
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-left text-sm">
                <thead><tr><th className="px-3 py-2">Sample</th><th className="px-3 py-2">Assay</th><th className="px-3 py-2">Subpanel</th><th className="px-3 py-2">Environment</th><th className="px-3 py-2">Sex</th><th className="px-3 py-2">Types</th><th className="px-3 py-2">Tiers</th><th className="px-3 py-2">Findings</th></tr></thead>
                <tbody>
                  {cohortQuery.data.samples.map((row) => (
                    <tr key={row.sample_name} className="border-t border-border">
                      <td className="px-3 py-2"><Link className="font-medium text-link hover:underline" to={sampleDetailPath(row, row.sample_name)}>{row.sample_name}</Link></td>
                      <td className="px-3 py-2">{row.asp_id || "-"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{row.subpanel_id || "-"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{row.environment || "-"}</td>
                      <td className="px-3 py-2">{row.sex ? humanSex(row.sex) : "Not recorded"}</td>
                      <td className="px-3 py-2"><div className="flex flex-wrap gap-1">{row.finding_types.map((type) => <TableBadge key={type} className={valueBadgeClass(type)}>{type}</TableBadge>)}</div></td>
                      <td className="px-3 py-2"><div className="flex gap-1">{row.tiers.map((tier) => <TableBadge key={tier} className={cn("border-transparent", tierClasses[String(tier)])}>{tier}</TableBadge>)}</div></td>
                      <td className="max-w-xl px-3 py-2 text-muted-foreground">{row.findings.join(", ") || "-"}</td>
                    </tr>
                  ))}
                  {!cohortQuery.data.samples.length && <tr><td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">No samples have a reported finding for this gene.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="content-section p-4">
            <h2 className="text-sm font-semibold">How prevalence is calculated</h2>
            <p className="type-body mt-1 text-muted-foreground">
              Prevalence is the number of eligible samples with a reported Tier 1-4 finding involving {gene}, divided by the number of eligible samples that profiled {gene}, multiplied by 100. Eligible samples are ready and visible to your account. For each enabled SNV, CNV, fusion, or translocation target, the denominator uses the sample&apos;s selected target-specific gene list and then the ASP covered-gene scope; a target with no gene restriction is treated as profiling every gene. {includeHistory
                ? `Findings are read from all saved report versions. Repeated occurrences of the same typed finding in multiple reports for one sample count once.`
                : `Findings are read only from each sample's latest saved report.`}
            </p>
            {includeHistory && cohortQuery.data.denominator.duplicate_report_observations_removed > 0 && (
              <p className="type-caption mt-2 text-muted-foreground">
                {cohortQuery.data.denominator.duplicate_report_observations_removed} repeated report occurrence(s) were removed from the calculation.
              </p>
            )}
            {cohortQuery.data.denominator.samples_excluded_outside_gene_scope > 0 && (
              <p className="type-caption mt-2 text-muted-foreground">
                {cohortQuery.data.denominator.samples_excluded_outside_gene_scope} ready sample(s) were outside the eligible target-specific gene scope.
              </p>
            )}
            {cohortQuery.data.truncated && <p className="mt-2 text-sm font-medium text-warning">The result reached its bounded response limit. Narrower access scope or operational review may be required for a complete export.</p>}
          </section>
        </div>
      )}
    </PageShell>
  )
}
