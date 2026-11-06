import { Fragment, useEffect } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError } from "@/lib/notifications"
import { StructuralTranscriptTable, type StructuralTranscriptRow } from "@/components/detail/StructuralTranscriptTable"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { FindingCommentComposer, FindingCommentLists } from "@/components/comments/FindingComments"
import { CallerBadges, ConsequenceBadges, StatusBadges } from "@/lib/variant-ui"
import { selectedTranslocationAnnotation, translocationGenes, translocationPositionLabel } from "@/lib/variant-helpers"
import {
  DetailDataTable,
  DetailMetricTable,
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
import { cbioportalOncoprintUrl, igvAlignmentLinks, pubmedSearchUrl } from "@/lib/external-links"
import { CosmicKnowledgeBlock, KnowledgebaseExplorer } from "@/components/detail/VariantKnowledgebase"

function supportFraction(value: unknown): number | null {
  const counts = typeof value === "string" ? value.split(",") : value
  if (!Array.isArray(counts) || counts.length !== 2) return null
  if (counts.some(count => (typeof count !== "number" && typeof count !== "string") || String(count).trim() === "")) return null
  const [reference, alternate] = counts.map(Number)
  if (![reference, alternate].every(count => Number.isFinite(count) && count >= 0)) return null
  return reference + alternate > 0 ? alternate / (reference + alternate) : null
}

function genotypeRows(translocation: any) {
  const rows = Array.isArray(translocation?.GT) ? translocation.GT : []
  return rows.map((gt: any) => ({
    ...gt,
    prPct: supportFraction(gt?.PR),
    srPct: supportFraction(gt?.SR),
  }))
}

export function TranslocationDetail() {
  const { id, varId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const access = useCurrentUserAccess()
  const transcriptSelection = useMutation({
    mutationFn: (key: string) => api.patch(
      `/samples/${id}/translocations/${varId}/selected-transcript`, { annotation_key: key },
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['translocation', id, varId] })
      queryClient.invalidateQueries({ queryKey: ['sample-translocations'] })
      queryClient.invalidateQueries({ queryKey: ['sample-comment-suggestion'] })
      queryClient.invalidateQueries({ queryKey: ['report-preview'] })
    },
    onError: err => notifyActionError("Unable to select transcript", err, "Transcript selection"),
  })

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['translocation', id, varId],
    queryFn: () => api.get(`/samples/${encodeURIComponent(id || "")}/translocations/${encodeURIComponent(varId || "")}`).then(res => res.data)
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
  const annRows: StructuralTranscriptRow[] = data.transcript_combinations || []
  const selectedKey = annRows.find(row => JSON.stringify(row.annotation) === JSON.stringify(annotation))?.annotation_key
  const position = translocationPositionLabel(translocation)
  const callers = translocation?.INFO?.variant_callers || translocation?.callers
  const readEvidence = genotypeRows(translocation)
  const supportValues = readEvidence.flatMap((row: { prPct: number | null; srPct: number | null }) =>
    [row.prPct, row.srPct].filter((value): value is number => value !== null))
  const maxSupport = supportValues.length ? Math.max(...supportValues) : null
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
        geneSeparator="::"
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
                <DetailField label="Genes">{genes.join("::") || "-"}</DetailField>
                <DetailField label="Position" valueClassName="text-primary/80">{position}</DetailField>
                <DetailField label="Type" valueClassName="uppercase">{translocation?.INFO?.SVTYPE || "-"}</DetailField>
                <DetailField label="Quality">{translocation?.QUAL ?? "-"}</DetailField>
                <DetailField label="Callers">{translocation?.INFO?.variant_callers || translocation?.callers || "-"}</DetailField>
                <DetailField label="Unique reads">{translocation?.INFO?.UNIQUE_READS || translocation?.unique_reads || "-"}</DetailField>
                <DetailField label="Status"><StatusBadges finding={translocation} /></DetailField>
                {readEvidence.map((row: { type?: string; sample?: string; PR?: unknown; SR?: unknown; prPct: number | null; srPct: number | null }, index: number) => <Fragment key={index}>
                  <DetailField label={`${row.type || row.sample || "Sample"} paired reads`}>
                    <span>{Array.isArray(row.PR) ? row.PR.join("/") : displayValue(row.PR)}</span>
                    <span className="ml-1 type-meta text-muted-foreground">{percentValue(row.prPct, 1)}</span>
                  </DetailField>
                  <DetailField label={`${row.type || row.sample || "Sample"} split reads`}>
                    <span>{Array.isArray(row.SR) ? row.SR.join("/") : displayValue(row.SR)}</span>
                    <span className="ml-1 type-meta text-muted-foreground">{percentValue(row.srPct, 1)}</span>
                  </DetailField>
                </Fragment>)}
                {!readEvidence.length && <DetailField label="Read evidence">No genotype read evidence available.</DetailField>}
              </FindingIdentityCard>

              <FindingCommentComposer
                sampleId={sampleRouteKey}
                resourceType="translocation"
                resource={translocation}
                assayGroup={data.assay_group}
                diagnosis={data.diagnosis}
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
              <p className="mb-2 type-body-sm text-muted-foreground">SnpEff annotations · selection: {translocation?.INFO?.ANN_selection_source?.replaceAll("_", " ") || "Not recorded"}</p>
              <StructuralTranscriptTable
                rows={annRows}
                selectedKey={selectedKey}
                canSelect={hasPermission(access.data, "translocation:manage")}
                pending={transcriptSelection.isPending}
                onSelect={key => transcriptSelection.mutate(key)}
                translations={data.snpeff_conseq_translations}
              />
            </DetailCard>

            {!!translocation?.source_records?.length && <DetailCard title="Source breakends">
              <p className="mb-2 type-body-sm text-muted-foreground">Both original records are retained. Display order does not indicate biological fusion direction.</p>
              <DetailDataTable rows={translocation.source_records} columns={[
                { key: "ID", header: "Source ID", render: (row: Record<string, unknown>) => String(row.ID ?? "-") },
                { key: "position", header: "Position", render: (row: Record<string, unknown>) => `${row.CHROM}:${row.POS}` },
                { key: "ALT", header: "Allele", render: (row: Record<string, unknown>) => String(row.ALT ?? "-") },
                { key: "record", header: "Evidence", render: (row: Record<string, unknown>) => <details><summary className="cursor-pointer type-meta">Annotations and read support</summary><pre className="max-h-64 overflow-auto type-body-sm">{JSON.stringify(row, null, 2)}</pre></details> },
              ]} />
            </DetailCard>}

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
              <DetailField label="SnpEff consequence"><ConsequenceBadges value={annotation?.Annotation} translations={data.snpeff_conseq_translations} wide /></DetailField>
              <DetailMetricTable
                metrics={[
                  { label: "Transcript", value: annotation?.Feature_ID || annotation?.Feature, monospace: true },
                  { label: "Protein", value: annotation?.HGVS_p || annotation?.HGVSp, monospace: true },
                  { label: "cDNA", value: annotation?.HGVS_c || annotation?.HGVSc, monospace: true },
                  { label: "Exon rank", value: annotation?.Rank || annotation?.EXON || annotation?.INTRON },
                  { label: "Biotype", value: annotation?.Transcript_BioType },
                  { label: "SnpEff impact", value: annotation?.Annotation_Impact },
                ]}
                dense
              />
            </DetailCard>

            <ExternalLinksCard
              links={[
                ...igvAlignmentLinks(data.bam_id, position, data.design_bed_paths),
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
