import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { CallerBadges, ConsequenceBadges, FilterFlagBadges, ImpactBadge, PredictionBadge } from "@/lib/variant-ui"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { displayValue, isPresent, percentValue } from "@/lib/detail-formatters"
import {
  DetailCard,
  DetailField,
  DetailFieldGrid,
  FindingDetailShell,
  FindingError,
  FindingHero,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"

function variantLocation(variant: any) {
  if (!variant) return "-"
  const ref = Array.isArray(variant.REF) ? variant.REF.join(",") : variant.REF
  const alt = Array.isArray(variant.ALT) ? variant.ALT.join(",") : variant.ALT
  return `${variant.CHROM}:${variant.POS} ${displayValue(ref)}>${displayValue(alt)}`
}

function clinicalSig(csq: any, variant: any) {
  return csq?.CLIN_SIG || variant?.INFO?.CLNSIG || variant?.INFO?.CLIN_SIG
}

function compactObjectSummary(value: any) {
  if (!value) return "-"
  if (typeof value === "string") return value
  if (Array.isArray(value)) return `${value.length} record(s)`
  if (typeof value === "object") {
    const preferred = ["highest_level", "oncogenic", "mutationEffect", "clinicalSignificance", "drug", "disease", "summary", "description", "name"]
    for (const key of preferred) {
      if (isPresent(value[key])) return displayValue(value[key])
    }
    return `${Object.keys(value).length} field(s)`
  }
  return displayValue(value)
}

function ponRows(value: any) {
  if (!value || typeof value !== "object") return []
  return Object.entries(value)
    .flatMap(([caller, callerValue]: [string, any]) => {
      if (!callerValue || typeof callerValue !== "object") return []
      return Object.entries(callerValue).map(([metric, metricValue]) => ({
        caller,
        metric,
        value: metricValue,
      }))
    })
}

function externalLinks(variant: any, csq: any, data: any) {
  const gene = csq?.SYMBOL
  const hgvsp = csq?.HGVSp
  const dbsnp = variant?.dbsnp_id
  const cosmic = Array.isArray(variant?.cosmic_ids) ? variant.cosmic_ids[0] : undefined
  const pubmed = Array.isArray(variant?.pubmed_ids) ? variant.pubmed_ids[0] : undefined
  const clinvar = variant?.INFO?.CLNACC
  const position = variant?.CHROM && variant?.POS ? `${variant.CHROM}:${variant.POS}` : ""

  return [
    data?.bam_id && position ? { label: "Open region in IGV", value: position, href: `http://localhost:60151/load?file=${encodeURIComponent(String(data.bam_id))}&locus=${encodeURIComponent(position)}` } : null,
    dbsnp ? { label: `dbSNP ${dbsnp}`, value: dbsnp, href: `https://www.ncbi.nlm.nih.gov/snp/${dbsnp}` } : null,
    cosmic ? { label: `COSMIC ${cosmic}`, value: cosmic, href: `https://cancer.sanger.ac.uk/cosmic/search?q=${encodeURIComponent(cosmic)}` } : null,
    clinvar ? { label: `ClinVar ${clinvar}`, value: clinvar, href: `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(clinvar)}` } : null,
    gene ? { label: `cBioPortal ${gene}`, value: gene, href: `https://www.cbioportal.org/results/oncoprint?gene_list=${encodeURIComponent(gene)}` } : null,
    gene ? { label: `OncoKB ${gene}`, value: gene, href: `https://www.oncokb.org/gene/${encodeURIComponent(gene)}` } : null,
    gene && hgvsp ? { label: "LitVar", value: `${gene} ${hgvsp}`, href: `https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?query=${encodeURIComponent(`${gene} ${hgvsp}`)}` } : null,
    pubmed ? { label: `PubMed ${pubmed}`, value: pubmed, href: `https://pubmed.ncbi.nlm.nih.gov/${pubmed}/` } : null,
  ].filter(Boolean) as any[]
}

export function VariantDetail() {
  const { id, varId } = useParams()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['variant', id, varId],
    queryFn: () => api.get(`/samples/${id}/small-variants/${varId}`).then(res => res.data)
  })
  const { data: filterFlagMetadata } = useQuery({
    queryKey: ["filter-flag-metadata"],
    queryFn: () => api.get("/public/filter-flags/metadata").then(res => res.data),
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) {
    return <FindingLoading />
  }

  if (error || !data) {
    return (
      <FindingError
        title="Error loading variant"
        message={error instanceof Error ? error.message : "Unknown error"}
        backTo={`/samples/${id}`}
      />
    )
  }

  const { variant, sample, latest_classification } = data
  const csq = variant?.INFO?.selected_CSQ || {}
  const transcripts = Array.isArray(variant?.INFO?.CSQ) ? variant.INFO.CSQ : []
  const callers = variant?.INFO?.variant_callers || variant?.callers || []
  const sampleHref = `/samples/${sample?._id || id}`

  const titleVariantId = csq.HGVSp && csq.HGVSp !== "-" ? csq.HGVSp : (csq.HGVSc || variant?.ALT?.[0] || "")

  return (
    <FindingDetailShell>
      <FindingHero
        backTo={`/samples/${id}`}
        title={csq.SYMBOL || "Unknown Gene"}
        subtitle={
          <div className="space-y-2">
            <span className="block text-xl font-bold text-muted-foreground">
              <ExpandableText text={titleVariantId} maxLength={30} className="inline-flex" />
            </span>
            <Link to={sampleHref} className="inline-flex w-max rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary">
              Sample {sample?.name || id}
            </Link>
          </div>
        }
        chips={
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-wide text-muted-foreground">Called by</span>
            <CallerBadges value={callers} />
          </div>
        }
        actions={
          <VariantActionButtons
            sampleId={id!}
            resourceType="small_variant"
            variant={variant}
            onUpdate={() => refetch()}
          />
        }
        statLabel="Max VAF"
        statValue={`${variant?.GT ? Math.max(...variant.GT.map((g: any) => g.AF * 100)).toFixed(1) : 0}%`}
      />

      <FindingMainGrid
        main={
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <DetailCard title="Variant Identity">
                <DetailFieldGrid>
                  <DetailField label="Gene">{csq.SYMBOL}</DetailField>
                  <DetailField label="Canonical transcript" valueClassName="font-mono text-primary/80">{csq.Feature}</DetailField>
                  <DetailField label="Consequence">
                    <ConsequenceBadges value={csq.Consequence} translations={data.vep_conseq_translations} />
                  </DetailField>
                  <DetailField label="Impact"><ImpactBadge value={csq.IMPACT} /></DetailField>
                  <DetailField label="Variant class">{data.vep_var_class_translations?.[variant?.variant_class]?.display_name || variant?.variant_class || csq.VARIANT_CLASS || "-"}</DetailField>
                  <DetailField label="Position" valueClassName="font-mono">{variantLocation(variant)}</DetailField>
                  <DetailField label="Filter flags"><FilterFlagBadges value={variant?.FILTER} metadata={filterFlagMetadata} /></DetailField>
                  <DetailField label="cDNA"><ExpandableText text={csq.HGVSc || "-"} maxLength={24} className="font-mono" /></DetailField>
                  <DetailField label="Protein"><ExpandableText text={csq.HGVSp || "-"} maxLength={24} className="font-mono" /></DetailField>
                  <DetailField label="Exon / Intron">{csq.EXON || csq.INTRON || "-"}</DetailField>
                  <DetailField label="Indel size">{variant?.INFO?.SVLEN || variant?.indel_size || "-"}</DetailField>
                </DetailFieldGrid>
              </DetailCard>

              <DetailCard title="Sample Genotype" tone="success">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-muted/50 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">VAF</th>
                        <th className="px-3 py-2">Alt Depth</th>
                        <th className="px-3 py-2">Total Depth</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/30">
                      {variant?.GT?.map((gt: any, i: number) => (
                        <tr key={i}>
                          <td className="px-3 py-2 capitalize font-semibold">{gt.type}</td>
                          <td className="px-3 py-2 font-mono">{(gt.AF * 100).toFixed(1)}%</td>
                          <td className="px-3 py-2 font-mono">{gt.VD}</td>
                          <td className="px-3 py-2 font-mono">{gt.DP}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </DetailCard>
            </div>

            <CommentsPanel
              sampleId={id!}
              title="Add Comment Or Annotation"
              resourceType="small_variant"
              resource={variant}
              comments={[]}
              showList={false}
              assayGroup={data.assay_group}
              subpanel={data.subpanel}
              queryKeys={[["variant", id, varId]]}
              enableSuggestion={false}
              livePreview={false}
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CommentsPanel
                sampleId={id!}
                title="Sample-Specific Variant Comments"
                resourceType="small_variant"
                resource={variant}
                comments={variant?.comments || []}
                showComposer={false}
                queryKeys={[["variant", id, varId]]}
              />
              <CommentsPanel
                sampleId={id!}
                title="Global Variant Annotations"
                resourceType="small_variant"
                resource={variant}
                comments={data.annotations || variant?.global_annotations || []}
                showComposer={false}
                allowHide={false}
                queryKeys={[["variant", id, varId]]}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <DetailCard title="Population Frequencies" tone="info">
                <DetailMetricTable
                  metrics={[
                    { label: "gnomAD", value: percentValue(variant?.gnomad_frequency, 4) },
                    { label: "gnomAD max", value: percentValue(variant?.gnomad_max, 4) },
                    { label: "ExAC", value: percentValue(variant?.exac_frequency, 4) },
                    { label: "1000G", value: percentValue(variant?.thousandG_frequency, 4) },
                  ]}
                  dense
                />
              </DetailCard>

              <DetailCard title="Prediction And Clinical Signals">
                <div className="space-y-2">
                  <DetailMetricTable
                    metrics={[
                      { label: "CADD", value: csq.CADD_PHRED, monospace: true },
                      { label: "ClinVar", value: clinicalSig(csq, variant) },
                      { label: "Callers", value: callers },
                      { label: "Selected by", value: variant?.INFO?.selected_CSQ_criteria },
                    ]}
                    dense
                  />
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="rounded-lg border border-border bg-background/50 p-2">
                      <span className="detail-field-label">SIFT</span>
                      <PredictionBadge value={csq.SIFT} />
                    </div>
                    <div className="rounded-lg border border-border bg-background/50 p-2">
                      <span className="detail-field-label">PolyPhen</span>
                      <PredictionBadge value={csq.PolyPhen} />
                    </div>
                  </div>
                </div>
              </DetailCard>
            </div>

            <DetailCard title="Panel Of Normals Evidence" tone="info">
              <DetailDataTable
                rows={ponRows(data.pon) || []}
                empty="No panel-of-normals evidence available."
                columns={[
                  { key: "caller", header: "Tool", render: (row: any) => row.caller || "-" },
                  { key: "metric", header: "Metric", render: (row: any) => row.metric || "-" },
                  { key: "value", header: "Value", render: (row: any) => displayValue(row.value) },
                ]}
              />
            </DetailCard>

            <DetailCard title="Transcript Consequences">
              <DetailDataTable
                rows={transcripts}
                empty="No alternate transcript annotations available."
                columns={[
                  { key: "gene", header: "Gene", render: (row: any) => (
                    <span className="inline-flex items-center gap-1.5">
                      <span>{row.SYMBOL || "-"}</span>
                      {row.Feature === csq.Feature ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : null}
                    </span>
                  ) },
                  { key: "feature", header: "Transcript", render: (row: any) => <span className="font-mono">{row.Feature || "-"}</span> },
                  { key: "hgvsc", header: "cDNA", render: (row: any) => <ExpandableText text={row.HGVSc || "-"} maxLength={28} className="font-mono" /> },
                  { key: "hgvsp", header: "Protein", render: (row: any) => <ExpandableText text={row.HGVSp || "-"} maxLength={28} className="font-mono" /> },
                  { key: "consequence", header: "Consequence", render: (row: any) => <ConsequenceBadges value={row.Consequence} translations={data.vep_conseq_translations} /> },
                  { key: "exon", header: "Exon/Intron", render: (row: any) => row.EXON || row.INTRON || "-" },
                  { key: "impact", header: "Impact", render: (row: any) => <ImpactBadge value={row.IMPACT} /> },
                ]}
              />
            </DetailCard>

            <DetailCard title="Knowledge Bases" tone="success">
              <DetailMetricTable
                metrics={[
                  { label: "CIViC variant", value: compactObjectSummary(data.civic) },
                  { label: "CIViC gene", value: compactObjectSummary(data.civic_gene) },
                  { label: "OncoKB variant", value: compactObjectSummary(data.oncokb) },
                  { label: "OncoKB action", value: compactObjectSummary(data.oncokb_action) },
                  { label: "OncoKB gene", value: compactObjectSummary(data.oncokb_gene) },
                  { label: "BRCA Exchange", value: compactObjectSummary(data.brca_exchange) },
                  { label: "IARC TP53", value: compactObjectSummary(data.iarc_tp53) },
                ]}
                dense
              />
            </DetailCard>
          </>
        }
        aside={
          <>
            <ClassificationsCard
              latest={latest_classification}
              other={data.other_classifications || variant?.additional_classifications || []}
              sampleId={id}
              resourceType="small_variant"
              resourceId={String(variant?._id || "")}
              onUpdate={() => refetch()}
            />

            <ExternalLinksCard links={externalLinks(variant, csq, data)} />

            <DetailCard title="Seen In Other Samples" tone="info">
              <DetailDataTable
                rows={data.in_other_samples || data.in_other || []}
                empty="No matching variants found in other samples."
                columns={[
                  { key: "sample", header: "Sample", render: (row: any) => row.sample_name || row.sample || row.SAMPLE || row.name || "-" },
                  { key: "assay", header: "Assay", render: (row: any) => row.assay || row.assay_group || "-" },
                  { key: "tier", header: "Tier", render: (row: any) => row.classification?.class || row.class || row.tier || "-" },
                ]}
              />
            </DetailCard>
          </>
        }
      />
    </FindingDetailShell>
  )
}
