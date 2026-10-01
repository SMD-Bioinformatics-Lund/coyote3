import { DataTable } from "@/components/data-table/DataTable";
import { GeneCohortCharts } from "@/components/gene-cohort/GeneCohortCharts";
import {
  GeneKnowledgebaseSummary
} from "@/components/knowledgebase/GeneKnowledgebaseSummary";
import { AppLoader } from "@/components/layout/AppLoader";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { TierBadge } from "@/lib/variant-ui";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Dna, Search, Users } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { humanSex, percent } from "./cohort-formatters";
import { MetricCard, PrevalenceBar } from "./cohort-presentation";
import { type GeneCohortPayload } from "./cohort-types";
import { useCohortColumns } from "./useCohortColumns";

export function GeneCohortExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedGene = (searchParams.get("gene") || "").trim().toUpperCase();
  const includeHistory = searchParams.get("history") === "1";
  const [geneInput, setGeneInput] = useState(requestedGene);

  const cohortQuery = useQuery<GeneCohortPayload>({
    queryKey: ["gene-cohort", requestedGene, includeHistory],
    queryFn: () =>
      api
        .get(
          `/common/gene/${encodeURIComponent(requestedGene)}/cohort-summary${includeHistory ? "?include_history=true" : ""}`,
        )
        .then((response) => response.data),
    enabled: Boolean(requestedGene),
  });

  const gene = cohortQuery.data?.query?.resolved_symbol || requestedGene;
  const hgncId = String(cohortQuery.data?.gene?.hgnc_id || cohortQuery.data?.gene?.HGNC_ID || "");
  const recurrentRows = useMemo(
    () => cohortQuery.data?.recurrent_findings || [],
    [cohortQuery.data?.recurrent_findings],
  );
  const { assayColumns, recurrentColumns, sampleColumns } = useCohortColumns();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalized = geneInput.trim().toUpperCase();
    if (!normalized) return;
    const nextParams = new URLSearchParams();
    nextParams.set("gene", normalized);
    if (includeHistory) nextParams.set("history", "1");
    setSearchParams(nextParams);
  };

  const setHistoryMode = (enabled: boolean) => {
    const nextParams = new URLSearchParams(searchParams);
    if (enabled) nextParams.set("history", "1");
    else nextParams.delete("history");
    setSearchParams(nextParams);
  };

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
            Enter an exact approved gene symbol or HGNC identifier to build an access-scoped cohort
            summary.
          </p>
        </section>
      )}

      {cohortQuery.isLoading && <AppLoader label="Loading gene cohort" />}
      {cohortQuery.error && (
        <section className="surface-panel border-destructive/40 p-5 text-destructive">
          {cohortQuery.error instanceof Error
            ? cohortQuery.error.message
            : "The gene cohort could not be loaded."}
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
                <Button variant="outline" size="sm">
                  Gene information
                </Button>
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
                detail={
                  includeHistory
                    ? "Distinct sample-finding pairs across report history"
                    : "Latest saved report per sample"
                }
              />
              <MetricCard
                label="Unique findings"
                value={cohortQuery.data.summary.unique_findings}
                detail="Distinct typed clinical finding identities"
              />
            </div>
          </section>

          <GeneKnowledgebaseSummary payload={cohortQuery.data.knowledgebase} />

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
                <p className="type-caption text-muted-foreground">
                  Finding samples divided by samples profiled for {gene} in each assay.
                </p>
              </div>
              <DataTable
                columns={assayColumns}
                data={cohortQuery.data.assays}
                stateKey="gene-cohort-assays"
                rowLabel="assays"
                searchPlaceholder="Search assays or groups..."
                enablePagination={false}
                hideExport
              />
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
                    <div className="flex items-center gap-2">
                      <TierBadge tier={tier} />
                      <span className="type-caption text-muted-foreground">Tier {tier}</span>
                    </div>
                    <strong className="text-xl font-semibold">
                      {cohortQuery.data.tier_counts[String(tier)] || 0}
                    </strong>
                  </div>
                ))}
              </div>
              <div className="mt-4 border-t border-border pt-4">
                <h3 className="text-sm font-semibold">Sex distribution</h3>
                <div className="mt-2 space-y-3">
                  {cohortQuery.data.sex_distribution.length ? (
                    cohortQuery.data.sex_distribution.map((row) => (
                      <div key={row.sex}>
                        <div className="mb-1 flex justify-between gap-3 text-sm">
                          <span>{humanSex(row.sex)}</span>
                          <span className="text-muted-foreground">
                            {row.finding_samples}/{row.profiled_samples} (
                            {percent(row.prevalence_percent)})
                          </span>
                        </div>
                        <PrevalenceBar value={row.prevalence_percent} />
                      </div>
                    ))
                  ) : (
                    <p className="type-body text-muted-foreground">
                      No sex information is available.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="surface-panel p-4">
            <div className="surface-panel-heading flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Recurrent findings</h2>
                <p className="type-caption text-muted-foreground">
                  Typed clinical findings ordered by the number of affected samples.
                </p>
              </div>
            </div>
            {recurrentRows.length ? (
              <DataTable
                columns={recurrentColumns}
                data={recurrentRows}
                stateKey="gene-cohort-recurrent"
                rowLabel="findings"
                searchPlaceholder="Search findings, genes, transcripts, or tiers..."
              />
            ) : (
              <p className="py-8 text-center text-muted-foreground">
                No reported findings were found.
              </p>
            )}
          </section>

          <section className="surface-panel p-4">
            <div className="surface-panel-heading flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              <div>
                <h2 className="text-base font-semibold">Samples with reported findings</h2>
                <p className="type-caption text-muted-foreground">
                  Samples are linked to their clinical workspace.
                </p>
              </div>
            </div>
            {cohortQuery.data.samples.length ? (
              <DataTable
                columns={sampleColumns}
                data={cohortQuery.data.samples}
                stateKey="gene-cohort-samples"
                rowLabel="samples"
                searchPlaceholder="Search samples, assays, subpanels, or findings..."
              />
            ) : (
              <p className="py-8 text-center text-muted-foreground">
                No samples have a reported finding for this gene.
              </p>
            )}
          </section>

          <section className="content-section p-4">
            <h2 className="text-sm font-semibold">How prevalence is calculated</h2>
            <p className="type-body mt-1 text-muted-foreground">
              Prevalence is the number of eligible samples with a reported Tier 1-4 finding
              involving {gene}, divided by the number of eligible samples that profiled {gene},
              multiplied by 100. Eligible samples are ready and visible to your account. For each
              enabled SNV, CNV, fusion, or translocation target, the denominator uses the
              sample&apos;s selected target-specific gene list and then the assay covered-gene scope;
              a target with no gene restriction is treated as profiling every gene.{" "}
              {includeHistory
                ? `Findings are read from all saved report versions. Repeated occurrences of the same typed finding in multiple reports for one sample count once.`
                : `Findings are read only from each sample's latest saved report.`}
            </p>
            {includeHistory &&
              cohortQuery.data.denominator.duplicate_report_observations_removed > 0 && (
                <p className="type-caption mt-2 text-muted-foreground">
                  {cohortQuery.data.denominator.duplicate_report_observations_removed} repeated
                  report occurrence(s) were removed from the calculation.
                </p>
              )}
            {cohortQuery.data.denominator.samples_excluded_outside_gene_scope > 0 && (
              <p className="type-caption mt-2 text-muted-foreground">
                {cohortQuery.data.denominator.samples_excluded_outside_gene_scope} ready sample(s)
                were outside the eligible target-specific gene scope.
              </p>
            )}
            {cohortQuery.data.truncated && (
              <p className="mt-2 text-sm font-medium text-warning">
                The result reached its bounded response limit. Narrower access scope or operational
                review may be required for a complete export.
              </p>
            )}
          </section>
        </div>
      )}
    </PageShell>
  );
}
