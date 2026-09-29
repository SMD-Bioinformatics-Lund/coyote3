import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, ExternalLink, Search, ZoomIn, ZoomOut } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { DetailDataTable } from "@/components/detail/DetailEvidenceCards"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { api } from "@/lib/api"
import { apiPath } from "@/lib/runtime-paths"
import { ConsequenceBadges, ImpactBadge, type ConsequenceMetadata } from "@/lib/variant-ui"

export type VepReference = {
  vep_id: string
  source: string
  vc_translation_source: string
  conseq_translation_source: string
  conseq_translations: Record<string, ConsequenceMetadata>
  consequence_groups: Record<string, string[]>
  variant_class_translations: Record<string, { short: string; desc: string; displayname: string; so_term: string }>
  db_info: Record<string, Record<string, string | number | Record<string, string> | null>>
  consequence_diagram: { mime_type: string; sha256: string; width: number; height: number; source_url: string; release: string } | null
}

function SourceLink({ href, children }: { href: string; children: React.ReactNode }) {
  if (!/^https?:\/\//i.test(href)) return <span>{children}</span>
  return <a href={href} target="_blank" rel="noreferrer" className="link-text inline-flex items-center gap-1 break-all">{children}<ExternalLink className="size-3 shrink-0" aria-hidden="true" /></a>
}

export default function VepReferencePage() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState("")
  const [group, setGroup] = useState("")
  const [impact, setImpact] = useState("")
  const [tab, setTab] = useState("consequences")
  const [zoom, setZoom] = useState(false)
  const versions = useQuery({ queryKey: ["public-vep-versions"], queryFn: () => api.get<{ versions: string[] }>("/public/vep").then(r => r.data), staleTime: 300_000 })
  const release = params.get("version") || versions.data?.versions[0] || ""
  const reference = useQuery({ queryKey: ["public-vep-reference", release], queryFn: () => api.get<VepReference>(`/public/vep/${encodeURIComponent(release)}`).then(r => r.data), enabled: Boolean(release), staleTime: 300_000 })
  const data = reference.data
  const needle = search.trim().toLowerCase()
  const terms = Object.entries(data?.conseq_translations || {}).map(([term, meta]) => ({ term, ...meta })).filter(row =>
    (!group || row.group === group) && (!impact || row.impact === impact) &&
    [row.term, row.desc, row.group, row.so_term, row.display].some(value => value?.toLowerCase().includes(needle)))
  const classes = Object.entries(data?.variant_class_translations || {}).map(([term, meta]) => ({ term, ...meta })).filter(row =>
    [row.term, row.desc, row.so_term, row.displayname].some(value => value.toLowerCase().includes(needle)))
  const diagram = data?.consequence_diagram
  const diagramAllowed = diagram && ["image/jpeg", "image/png", "image/svg+xml"].includes(diagram.mime_type) && diagram.release === data?.vep_id
  const ontology = (term?: string, kind = "current_svn") => term && /^SO:\d{7}$/.test(term)
    ? <SourceLink href={`http://www.sequenceontology.org/miso/${kind}/term/${term}`}>{term}</SourceLink> : <span>{term || "-"}</span>

  return <PageShell title="VEP Reference" eyebrow="Reference library" actions={<Link to="/about" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2"><ArrowLeft className="size-4" />About Coyote3</Link>}>
    <section className="surface-panel space-y-4 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1 type-label">VEP release
          <select aria-label="VEP release" value={release} className="paper-inset block rounded-md p-2" onChange={event => { setParams({ version: event.target.value }); setGroup(""); setImpact("") }}>
            {!versions.data?.versions.length && <option value="">No releases installed</option>}
            {release && !versions.data?.versions.includes(release) && <option value={release}>{release} (not installed)</option>}
            {versions.data?.versions.map(version => <option key={version} value={version}>{version}</option>)}
          </select>
        </label>
        {data && <p className="type-meta text-muted-foreground">{Object.keys(data.conseq_translations).length} consequences · {Object.keys(data.consequence_groups).length} groups · {Object.keys(data.variant_class_translations).length} variant classes</p>}
      </div>
      {(versions.isLoading || reference.isLoading) && <AppLoader label="Loading VEP reference" />}
      {(versions.isError || reference.isError) && <div role="alert" className="flex flex-wrap items-center gap-3"><p>Unable to load the selected VEP reference.</p><Button variant="outline" onClick={() => { void versions.refetch(); void reference.refetch() }}>Retry</Button></div>}
      {!versions.isLoading && !versions.isError && !versions.data?.versions.length && <p>No VEP references are installed.</p>}
      {data && <>
        <details open>
          <summary className="cursor-pointer py-2 type-section-title">Consequence locations · Ensembl {data.vep_id}</summary>
          {diagramAllowed ? <figure className="w-fit max-w-full space-y-2">
            <div className="max-w-full overflow-x-auto rounded-md"><img src={apiPath(`/public/vep/${encodeURIComponent(data.vep_id)}/diagram`)} width={diagram.width} height={diagram.height} alt={`Ensembl ${data.vep_id} variant consequences relative to transcript structure`} className={zoom ? "vep-reference-diagram block h-auto max-w-none" : "vep-reference-diagram block h-auto max-w-full"} style={{ width: zoom ? diagram.width : Math.min(diagram.width, 760) }} /></div>
            <figcaption className="flex flex-wrap items-center justify-between gap-2 type-meta text-muted-foreground"><span><SourceLink href={data.conseq_translation_source}>Ensembl diagram source</SourceLink> · Release {diagram.release}</span><Button variant="outline" size="icon" aria-label={zoom ? "Fit diagram" : "Zoom diagram"} title={zoom ? "Fit diagram" : "Zoom diagram"} onClick={() => setZoom(value => !value)}>{zoom ? <ZoomOut className="size-4" /> : <ZoomIn className="size-4" />}</Button></figcaption>
          </figure> : <p className="type-body-sm text-muted-foreground">No diagram is installed for this release.</p>}
        </details>
        <SegmentedControl ariaLabel="VEP reference tables" value={tab} onValueChange={setTab} items={[{ value: "consequences", label: <span className="type-meta normal-case tracking-normal">Consequences</span> }, { value: "classes", label: <span className="type-meta normal-case tracking-normal">Variant classes</span> }, { value: "cache", label: <span className="type-meta normal-case tracking-normal">Cache sources</span> }]} />
        {tab !== "cache" && <div className="flex flex-wrap items-center gap-3">
          <div className="flex min-w-0 basis-full items-center gap-2 sm:flex-1 sm:basis-64"><Search className="size-4 shrink-0" aria-hidden="true" /><Input aria-label="Search VEP terms" placeholder="Search terms, descriptions or SO accessions" value={search} onChange={event => setSearch(event.target.value)} /></div>
          {tab === "consequences" && <>
            <select aria-label="Consequence group" className="paper-inset max-w-full rounded-md p-2" value={group} onChange={event => setGroup(event.target.value)}><option value="">All groups</option>{Object.keys(data.consequence_groups).map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select>
            <select aria-label="Consequence impact" className="paper-inset rounded-md p-2" value={impact} onChange={event => setImpact(event.target.value)}><option value="">All impacts</option>{[...new Set(Object.values(data.conseq_translations).map(meta => meta.impact).filter(Boolean))].map(value => <option key={value} value={value}>{value}</option>)}</select>
          </>}
        </div>}
        {tab === "consequences" && <>
          <p className="type-meta text-muted-foreground">Ensembl impact ratings describe predicted effects, not clinical pathogenicity. Groups are Coyote3 filter categories. {terms.length} matching terms.</p>
          <div className="overflow-x-auto"><div className="min-w-[760px]"><DetailDataTable key={`${release}-${group}-${impact}-${search}`} rows={terms} initialRows={10} tableLayout="fixed" empty="No matching consequence terms." columns={[
            { key: "term", header: "Consequence", className: "w-1/4 break-words", render: row => <ConsequenceBadges value={row.term} translations={data.conseq_translations} compact={false} wide /> },
            { key: "group", header: "Group", className: "w-1/6 break-words", render: row => row.group?.replaceAll("_", " ") },
            { key: "impact", header: "Impact", className: "w-1/6", render: row => <ImpactBadge value={row.impact} /> },
            { key: "so", header: "Sequence Ontology", className: "w-1/6", render: row => ontology(row.so_term) },
            { key: "desc", header: "Description", className: "break-words", render: row => row.desc },
          ]} /></div></div>
          <SourceLink href={data.conseq_translation_source}>Consequence definitions source</SourceLink>
        </>}
        {tab === "classes" && <><DetailDataTable key={`${release}-${search}`} rows={classes} initialRows={10} tableLayout="fixed" empty="No matching variant classes." columns={[
          { key: "term", header: "Variant class", className: "w-1/4 break-words", render: row => row.term },
          { key: "so", header: "Sequence Ontology", className: "w-1/4", render: row => ontology(row.so_term, "current_release") },
          { key: "desc", header: "Description", className: "break-words", render: row => row.desc },
        ]} /><SourceLink href={data.vc_translation_source}>Variant classification source</SourceLink></>}
        {tab === "cache" && <>
          <p className="type-meta text-muted-foreground">Published Ensembl cache versions, not the databases used by an individual sample's pipeline.</p>
          {Object.entries(data.db_info).map(([build, info]) => <section key={build} className="space-y-2"><h2 className="type-section-title">{build}</h2><DetailDataTable rows={Object.entries(info.published_sources && typeof info.published_sources === "object" ? info.published_sources : info).filter(([, value]) => typeof value === "string" || typeof value === "number")} tableLayout="fixed" columns={[
            { key: "source", header: "Source", className: "w-1/3 break-words", render: row => row[0].replaceAll("_", " ") },
            { key: "version", header: "Version", className: "break-words", render: row => String(row[1] || "Not published") },
          ]} /></section>)}
          <SourceLink href={data.source}>Cache documentation source</SourceLink>
        </>}
      </>}
    </section>
  </PageShell>
}
