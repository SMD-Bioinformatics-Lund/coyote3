import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { CallerBadges } from "@/lib/variant-ui"
import { selectedTranslocationAnnotation, translocationGenes, translocationPositionLabel } from "@/lib/variant-helpers"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { displayValue, percentValue } from "@/lib/detail-formatters"
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

function translatedConsequence(annotation: any, translations: Record<string, any> = {}) {
  const raw = annotation?.Annotation || annotation?.Consequence
  const terms = Array.isArray(raw) ? raw : String(raw || "").split("&").filter(Boolean)
  if (!terms.length) return "-"
  return terms
    .map((term: string) => translations?.[term]?.display_name || translations?.[term]?.label || term.replace(/_/g, " "))
    .join(", ")
}

function genotypeRows(translocation: any) {
  const rows = Array.isArray(translocation?.GT) ? translocation.GT : []
  return rows.map((gt: any) => ({
    ...gt,
    prPct: Number(gt?.PR?.[1]) / Math.max(Number(gt?.PR?.[0]) + Number(gt?.PR?.[1]), 1),
    srPct: Number(gt?.SR?.[1]) / Math.max(Number(gt?.SR?.[0]) + Number(gt?.SR?.[1]), 1),
  }))
}

export function TranslocationDetail() {
  const { id, varId } = useParams()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['translocation', id, varId],
    queryFn: () => api.get(`/samples/${id}/translocations/${varId}`).then(res => res.data)
  })

  if (isLoading) {
    return <FindingLoading />
  }

  if (error || !data) {
    return (
      <FindingError
        title="Error loading translocation"
        message={error instanceof Error ? error.message : "Unknown error"}
        backTo={`/samples/${id}`}
      />
    )
  }

  const translocation = data.translocation || data.variant
  const { sample, latest_classification } = data
  const annotation = selectedTranslocationAnnotation(translocation)
  const genes = translocationGenes(translocation)
  const annRows = Array.isArray(translocation?.INFO?.ANN) ? translocation.INFO.ANN : []
  const position = translocationPositionLabel(translocation)
  const callers = translocation?.INFO?.variant_callers || translocation?.callers
  const sampleHref = `/samples/${sample?._id || id}`

  return (
    <FindingDetailShell>
      <FindingHero
        backTo={`/samples/${id}`}
        title={genes.length > 0 ? genes.join(" - ") : "Unknown Translocation"}
        chips={
          <>
            <span className="soft-chip">Translocation</span>
            <span className="soft-chip">{position}</span>
            <CallerBadges value={callers} />
            <Link to={sampleHref} className="soft-chip hover:bg-primary/15 hover:text-primary">
              Sample {sample?.name || id}
            </Link>
          </>
        }
        actions={
          <VariantActionButtons
            sampleId={id!}
            resourceType="translocation"
            variant={translocation}
            onUpdate={() => refetch()}
          />
        }
      />

      <FindingMainGrid
        main={
          <>
            <CommentsPanel
              sampleId={id!}
              title="Add Comment Or Annotation"
              resourceType="translocation"
              resource={translocation}
              comments={[]}
              showList={false}
              assayGroup={data.assay_group}
              subpanel={data.subpanel}
              queryKeys={[["translocation", id, varId]]}
              enableSuggestion={false}
              livePreview={false}
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CommentsPanel
                sampleId={id!}
                title="Sample-Specific Translocation Comments"
                resourceType="translocation"
                resource={translocation}
                comments={translocation?.comments || []}
                showComposer={false}
                queryKeys={[["translocation", id, varId]]}
              />
              <CommentsPanel
                sampleId={id!}
                title="Global Translocation Annotations"
                resourceType="translocation"
                resource={translocation}
                comments={data.annotations || []}
                showComposer={false}
                allowHide={false}
                queryKeys={[["translocation", id, varId]]}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <DetailCard title="Translocation Properties">
                <DetailFieldGrid>
                  <DetailField label="Genes">{genes.join(" - ") || "-"}</DetailField>
                  <DetailField label="Position" valueClassName="font-mono text-primary/80">{position}</DetailField>
                  <DetailField label="Type" valueClassName="uppercase">{translocation?.INFO?.SVTYPE || "-"}</DetailField>
                  <DetailField label="Quality" valueClassName="font-mono">{translocation?.QUAL ?? "-"}</DetailField>
                  <DetailField label="Callers">{translocation?.INFO?.variant_callers || translocation?.callers || "-"}</DetailField>
                  <DetailField label="Unique reads">{translocation?.INFO?.UNIQUE_READS || translocation?.unique_reads || "-"}</DetailField>
                </DetailFieldGrid>
              </DetailCard>

              <DetailCard title="Selected Annotation" tone="success">
                <DetailMetricTable
                  metrics={[
                    { label: "Transcript", value: annotation?.Feature_ID || annotation?.Feature, monospace: true },
                    { label: "Protein", value: annotation?.HGVS_p || annotation?.HGVSp, monospace: true },
                    { label: "cDNA", value: annotation?.HGVS_c || annotation?.HGVSc, monospace: true },
                    { label: "Consequence", value: translatedConsequence(annotation, data.vep_conseq_translations) },
                    { label: "Exon rank", value: annotation?.Rank || annotation?.EXON || annotation?.INTRON },
                    { label: "Biotype", value: annotation?.BioType || annotation?.BIOTYPE },
                  ]}
                  dense
                />
              </DetailCard>
            </div>

            <DetailCard title="Transcript Combinations">
              <DetailDataTable
                rows={annRows}
                empty="No alternate transcript combinations available."
                columns={[
                  { key: "selected", header: "", render: (row: any) => row === annotation ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : null },
                  { key: "gene", header: "Genes", render: (row: any) => displayValue(row.Gene_Name || row.SYMBOL) },
                  { key: "feature", header: "Transcript", render: (row: any) => <span className="font-mono">{row.Feature_ID || row.Feature || "-"}</span> },
                  { key: "protein", header: "Protein", render: (row: any) => row.HGVS_p || row.HGVSp || "-" },
                  { key: "cdna", header: "cDNA", render: (row: any) => row.HGVS_c || row.HGVSc || "-" },
                  { key: "consequence", header: "Consequence", render: (row: any) => translatedConsequence(row, data.vep_conseq_translations) },
                ]}
              />
            </DetailCard>

            <DetailCard title="Sample Read Evidence" tone="info">
              <DetailDataTable
                rows={genotypeRows(translocation)}
                empty="No genotype read evidence available."
                columns={[
                  { key: "type", header: "Type", render: (row: any) => row.type || row.sample || "-" },
                  { key: "pr", header: "PR", render: (row: any) => Array.isArray(row.PR) ? row.PR.join("/") : displayValue(row.PR) },
                  { key: "prpct", header: "PR %", render: (row: any) => percentValue(row.prPct, 1) },
                  { key: "sr", header: "SR", render: (row: any) => Array.isArray(row.SR) ? row.SR.join("/") : displayValue(row.SR) },
                  { key: "srpct", header: "SR %", render: (row: any) => percentValue(row.srPct, 1) },
                ]}
              />
            </DetailCard>
          </>
        }
        aside={
          <>
            <ClassificationsCard
              latest={latest_classification}
              other={data.other_classifications || []}
              sampleId={id}
              resourceType="translocation"
              resourceId={String(translocation?._id || "")}
              onUpdate={() => refetch()}
            />

            <ExternalLinksCard
              links={[
                data.bam_id && position !== "-"
                  ? { label: "Open junction in IGV", value: position, href: `http://localhost:60151/load?file=${encodeURIComponent(String(data.bam_id))}&locus=${encodeURIComponent(position)}` }
                  : null,
                genes[0]
                  ? { label: `cBioPortal ${genes[0]}`, value: genes[0], href: `https://www.cbioportal.org/results/oncoprint?gene_list=${encodeURIComponent(genes.join("%20"))}` }
                  : null,
                genes.length >= 2
                  ? { label: "PubMed gene pair", value: genes.join(" "), href: `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(genes.join(" "))}` }
                  : null,
              ].filter(Boolean) as any[]}
            />
          </>
        }
      />
    </FindingDetailShell>
  )
}
