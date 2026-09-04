import { useEffect } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { FindingCommentComposer, FindingCommentLists } from "@/components/comments/FindingComments"
import { CallerBadges, StatusBadges } from "@/lib/variant-ui"
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
  FindingDetailShell,
  FindingError,
  FindingCallerMeta,
  FindingDetailHero,
  FindingIdentityCard,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"
import { cbioportalOncoprintUrl, igvLoadUrl, pubmedSearchUrl } from "@/lib/external-links"
import { CosmicKnowledgeBlock, KnowledgebaseExplorer } from "@/components/detail/VariantKnowledgebase"

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
  const navigate = useNavigate()
  const location = useLocation()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['translocation', id, varId],
    queryFn: () => api.get(`/samples/${id}/translocations/${varId}`).then(res => res.data)
  })
  const routeSample = data?.sample
  useEffect(() => {
    if (routeSample?.name && id && varId && id !== routeSample.name) {
      navigate(sampleFindingPath(routeSample, id, "translocation", varId), {
        replace: true,
        state: location.state,
      })
    }
  }, [id, location.state, navigate, routeSample, routeSample?.name, varId])

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
  const readEvidence = genotypeRows(translocation)
  const maxSupport = readEvidence.reduce(
    (max: number, row: any) => Math.max(max, row.prPct || 0, row.srPct || 0),
    0,
  )
  const sampleRouteKey = sampleUrlKey(sample, id)
  const sampleHref = sampleDetailTabPath(sample, id, "translocations")
  const previousSampleHref = typeof location.state === "object" && location.state && "from" in location.state
    ? String((location.state as { from?: string }).from || sampleHref)
    : sampleHref

  return (
    <FindingDetailShell>
      <FindingDetailHero
        backTo={previousSampleHref}
        genes={genes}
        identity={`Translocation · ${position}`}
        sampleHref={sampleHref}
        sampleName={sample?.name || id}
        callers={
          <FindingCallerMeta>
            <CallerBadges value={callers} />
          </FindingCallerMeta>
        }
        actions={
          <VariantActionButtons
            sampleId={sampleRouteKey}
            resourceType="translocation"
            variant={translocation}
            onUpdate={() => refetch()}
          />
        }
        statLabel="Max support"
        statValue={percentValue(maxSupport, 1)}
      />

      <FindingMainGrid
        main={
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <FindingIdentityCard title="Translocation Identity">
                <DetailField label="Genes">{genes.join(" - ") || "-"}</DetailField>
                <DetailField label="Position" valueClassName="text-primary/80">{position}</DetailField>
                <DetailField label="Type" valueClassName="uppercase">{translocation?.INFO?.SVTYPE || "-"}</DetailField>
                <DetailField label="Quality">{translocation?.QUAL ?? "-"}</DetailField>
                <DetailField label="Callers">{translocation?.INFO?.variant_callers || translocation?.callers || "-"}</DetailField>
                <DetailField label="Unique reads">{translocation?.INFO?.UNIQUE_READS || translocation?.unique_reads || "-"}</DetailField>
                <DetailField label="Status"><StatusBadges finding={translocation} /></DetailField>
              </FindingIdentityCard>

              <FindingCommentComposer
                sampleId={sampleRouteKey}
                resourceType="translocation"
                resource={translocation}
                assayGroup={data.assay_group}
                subpanel={data.subpanel}
                queryKeys={[["translocation", id, varId]]}
              />
            </div>

            <FindingCommentLists
              sampleId={sampleRouteKey}
              resourceType="translocation"
              resource={translocation}
              queryKeys={[["translocation", id, varId]]}
              findingLabel="Translocation"
              sampleComments={translocation?.comments || []}
              globalComments={data.annotations || []}
            />

            <DetailCard title="Knowledge Bases" tone="success">
              <KnowledgebaseExplorer>
                <CosmicKnowledgeBlock evidence={data.cosmic} />
              </KnowledgebaseExplorer>
            </DetailCard>

            <DetailCard title="Transcript Combinations">
              <DetailDataTable
                rows={annRows}
                empty="No alternate transcript combinations available."
                columns={[
                  { key: "selected", header: "", render: (row: any) => row === annotation ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : null },
                  { key: "gene", header: "Genes", render: (row: any) => displayValue(row.Gene_Name || row.SYMBOL) },
                  { key: "feature", header: "Transcript", render: (row: any) => <span className="">{row.Feature_ID || row.Feature || "-"}</span> },
                  { key: "protein", header: "Protein", render: (row: any) => row.HGVS_p || row.HGVSp || "-" },
                  { key: "cdna", header: "cDNA", render: (row: any) => row.HGVS_c || row.HGVSc || "-" },
                  { key: "consequence", header: "Consequence", render: (row: any) => translatedConsequence(row, data.vep_conseq_translations) },
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

            <DetailCard title="Sample Read Evidence" tone="info">
              <div className="space-y-2">
                {readEvidence.map((row: any, index: number) => (
                  <div key={index} className="rounded-lg border border-border/70 bg-background/55 p-2.5">
                    <EvidenceBadge tone="info">{row.type || row.sample || "Sample"}</EvidenceBadge>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div>
                        <span className="detail-field-label">Paired reads</span>
                        <span className="type-body-sm font-semibold text-foreground">
                          {Array.isArray(row.PR) ? row.PR.join("/") : displayValue(row.PR)}
                        </span>
                        <span className="ml-1 type-meta text-muted-foreground">{percentValue(row.prPct, 1)}</span>
                      </div>
                      <div>
                        <span className="detail-field-label">Split reads</span>
                        <span className="type-body-sm font-semibold text-foreground">
                          {Array.isArray(row.SR) ? row.SR.join("/") : displayValue(row.SR)}
                        </span>
                        <span className="ml-1 type-meta text-muted-foreground">{percentValue(row.srPct, 1)}</span>
                      </div>
                    </div>
                  </div>
                ))}
                {!readEvidence.length ? (
                  <p className="type-body-sm text-muted-foreground">No genotype read evidence available.</p>
                ) : null}
              </div>
            </DetailCard>

            <ExternalLinksCard
              links={[
                data.bam_id && position !== "-" && igvLoadUrl(data.bam_id, position)
                  ? { label: "Open junction in IGV", value: position, href: igvLoadUrl(data.bam_id, position)! }
                  : null,
                genes[0]
                  ? { label: `cBioPortal ${genes[0]}`, value: genes[0], href: cbioportalOncoprintUrl(genes) }
                  : null,
                genes.length >= 2
                  ? { label: "PubMed gene pair", value: genes.join(" "), href: pubmedSearchUrl(genes.join(" ")) }
                  : null,
              ].filter(Boolean) as any[]}
            />
          </>
        }
      />
    </FindingDetailShell>
  )
}
