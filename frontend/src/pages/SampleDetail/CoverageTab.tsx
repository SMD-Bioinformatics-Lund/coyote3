import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Activity, AlertTriangle } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { shortCount } from "@/lib/detail-formatters"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

function flattenCoverageTable(covTable: any) {
  return Object.entries(covTable || {}).flatMap(([gene, regions]: [string, any]) =>
    Object.entries(regions || {}).map(([region, row]: [string, any]) => ({
      gene,
      region,
      ...row,
    })),
  )
}

function metric(value: unknown) {
  return shortCount(value, "-")
}

function coord(row: any) {
  const chr = row?.chr || row?.chrom || "-"
  return `${chr}:${row?.start || "-"}-${row?.end || "-"}`
}

function coverageNumber(row: any) {
  const value = Number(row?.cov)
  return Number.isFinite(value) ? value : Number.NaN
}

function regionLength(row: any) {
  const start = Number(row?.start)
  const end = Number(row?.end)
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : 0
}

function CoverageGeneView({
  gene,
  geneData,
  cutoff,
  smpGrp,
}: {
  gene: string
  geneData: any
  cutoff: number
  smpGrp: string
}) {
  const [zoom, setZoom] = useState(1)
  const [activeTab, setActiveTab] = useState<"exons" | "probes">("exons")
  const [infoTab, setInfoTab] = useState<"transcript" | "exons" | "cds" | "probes">("transcript")
  const transcript = geneData?.transcript || {}
  const exons = Array.isArray(geneData?.exons) ? geneData.exons : []
  const cds = Array.isArray(geneData?.CDS) ? geneData.CDS : []
  const probes = Array.isArray(geneData?.probes) ? geneData.probes : []
  const lowExons = cds.filter((row: any) => coverageNumber(row) < cutoff)
  const lowProbes = probes.filter((row: any) => coverageNumber(row) < cutoff)
  const start = Number(transcript.start || Math.min(...[...exons, ...cds, ...probes].map((row: any) => Number(row.start)).filter(Number.isFinite)))
  const end = Number(transcript.end || Math.max(...[...exons, ...cds, ...probes].map((row: any) => Number(row.end)).filter(Number.isFinite)))
  const safeStart = Number.isFinite(start) ? start : 0
  const safeEnd = Number.isFinite(end) && end > safeStart ? end : safeStart + 1
  const width = Math.max(760, Math.round(980 * zoom))
  const height = 245
  const margin = { left: 48, right: 28 }
  const transcriptChr = transcript.chr || transcript.chrom || exons[0]?.chr || cds[0]?.chr || probes[0]?.chr || "-"
  const transcriptLength = safeEnd - safeStart
  const x = (value: unknown) => {
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return margin.left
    return margin.left + ((numeric - safeStart) / (safeEnd - safeStart)) * (width - margin.left - margin.right)
  }

  const blacklist = useMutation({
    mutationFn: ({ row, region }: { row?: any; region: string }) =>
      api.post("/coverage/blacklist/entries", {
        gene,
        region,
        coord: row ? coord(row) : "",
        smp_grp: smpGrp,
      }),
    onSuccess: (_result, variables) => {
      notifySuccess("Coverage region blacklisted", `${gene} ${variables.region} was added to the blacklist.`, "Coverage")
    },
    onError: (error) => {
      notifyActionError("Unable to blacklist coverage region", error, "Coverage")
    },
  })

  const renderRows = (rows: any[], region: "CDS" | "probe") => (
    <div className="max-h-72 overflow-auto rounded-lg border border-border bg-background/70">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-muted text-[10px] uppercase tracking-wider text-muted-foreground">
          <tr>
            {region === "CDS" && <th className="px-2 py-2">Exon</th>}
            <th className="px-2 py-2">Coordinates</th>
            <th className="px-2 py-2">Coverage</th>
            <th className="px-2 py-2">Size</th>
            <th className="px-2 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${coord(row)}-${index}`} className="border-t border-border/60">
              {region === "CDS" && <td className="px-2 py-2 font-mono">{row.nbr || row.exon || "-"}</td>}
              <td className="px-2 py-2 font-mono">{coord(row)}</td>
              <td className="px-2 py-2 font-mono font-bold text-fail">{coverageNumber(row).toFixed(2)}X</td>
              <td className="px-2 py-2 font-mono">{metric(regionLength(row))}</td>
              <td className="px-2 py-2">
                <button
                  onClick={() => blacklist.mutate({ row, region })}
                  disabled={blacklist.isPending}
                  className="rounded-md border border-fail/30 bg-fail/10 px-2 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
                >
                  Blacklist
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={region === "CDS" ? 5 : 4} className="px-3 py-6 text-center text-muted-foreground">
                No low-coverage {region === "CDS" ? "exons" : "probes"} below {cutoff}X.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )

  const coverageValues = [...cds, ...probes]
    .map((row: any) => coverageNumber(row))
    .filter(Number.isFinite)
  const minCoverage = coverageValues.length ? Math.min(...coverageValues) : Number.NaN
  const avgCoverage = coverageValues.length
    ? coverageValues.reduce((sum: number, value: number) => sum + value, 0) / coverageValues.length
    : Number.NaN

  const transcriptRows = Object.entries(transcript || {}).filter(([, value]) => value !== undefined && value !== null && value !== "")

  const renderAllFeatureRows = (rows: any[], region: "exon" | "CDS" | "probe") => (
    <div className="max-h-96 overflow-auto rounded-lg border border-border bg-background/70">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-muted text-[10px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-2 py-2">Feature</th>
            <th className="px-2 py-2">Coordinates</th>
            <th className="px-2 py-2">Size</th>
            <th className="px-2 py-2">Coverage</th>
            <th className="px-2 py-2">Status</th>
            {region === "probe" && <th className="px-2 py-2">Overlapping exons</th>}
            <th className="px-2 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any, index: number) => {
            const cov = coverageNumber(row)
            const isLow = Number.isFinite(cov) && cov < cutoff
            const featureLabel = row.nbr || row.exon || row.name || row.id || `${region} ${index + 1}`
            const overlapping = Array.isArray(row.exon_nr)
              ? row.exon_nr.map((item: any) => item.nbr || item.exon || item).join(", ")
              : row.exon_nr || "-"
            return (
              <tr key={`${region}-${coord(row)}-${index}`} className="border-t border-border/60">
                <td className="px-2 py-2 font-mono">{featureLabel}</td>
                <td className="px-2 py-2 font-mono">{coord(row)}</td>
                <td className="px-2 py-2 font-mono">{metric(regionLength(row))}</td>
                <td className={`px-2 py-2 font-mono font-bold ${isLow ? "text-fail" : "text-pass"}`}>
                  {Number.isFinite(cov) ? `${cov.toFixed(2)}X` : "N/A"}
                </td>
                <td className="px-2 py-2">
                  <span className={`rounded-md px-2 py-1 text-[10px] font-bold uppercase ${isLow ? "bg-fail/10 text-fail" : "bg-pass/10 text-pass"}`}>
                    {Number.isFinite(cov) ? (isLow ? "Low" : "Pass") : "No design"}
                  </span>
                </td>
                {region === "probe" && <td className="px-2 py-2 font-mono">{overlapping}</td>}
                <td className="px-2 py-2">
                  {(region === "CDS" || region === "probe") && (
                    <button
                      onClick={() => blacklist.mutate({ row, region })}
                      disabled={blacklist.isPending}
                      className="rounded-md border border-fail/30 bg-fail/10 px-2 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
                    >
                      Blacklist
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
          {!rows.length && (
            <tr>
              <td colSpan={region === "probe" ? 7 : 6} className="px-3 py-6 text-center text-muted-foreground">
                No {region} data available for this gene.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )

  return (
    <section className="rounded-xl border border-cyan-200 border-t-4 border-t-cyan-500 bg-cyan-50/30 p-3 shadow-sm dark:bg-cyan-950/10">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
        <div>
          <h3 className="text-sm font-black uppercase tracking-wide">Gene: {gene} @ {cutoff}X</h3>
          <p className="text-xs text-muted-foreground">
            Transcript {metric(safeStart)}-{metric(safeEnd)} • {cds.length} CDS • {probes.length} probes
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="rounded-md border border-border bg-background px-2 py-1 text-xs font-bold hover:bg-muted" onClick={() => setZoom((value) => Math.max(0.5, value / 1.25))}>Zoom out</button>
          <button className="rounded-md border border-border bg-background px-2 py-1 text-xs font-bold hover:bg-muted" onClick={() => setZoom((value) => Math.min(8, value * 1.25))}>Zoom in</button>
          <button className="rounded-md border border-border bg-background px-2 py-1 text-xs font-bold hover:bg-muted" onClick={() => setZoom(1)}>Reset</button>
          <span className="rounded-md border border-border bg-background px-2 py-1 text-xs font-bold">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => blacklist.mutate({ region: "" })}
            disabled={blacklist.isPending}
            className="rounded-md border border-fail/30 bg-fail/10 px-2.5 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
          >
            Blacklist gene
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-background p-2">
        <svg width={width} height={height} role="img" aria-label={`${gene} coverage plot`}>
          <text x={margin.left} y={20} className="fill-foreground text-[14px] font-bold">
            {gene}
          </text>
          <text x={margin.left} y={38} className="fill-muted-foreground text-[11px]">
            {transcriptChr}:{metric(safeStart)}-{metric(safeEnd)} • {metric(transcriptLength)} bp • cutoff {cutoff}X
          </text>
          <text x={Math.max(margin.left + 300, width - 260)} y={20} className="fill-muted-foreground text-[11px]">
            Exons {exons.length} • CDS {cds.length} • Probes {probes.length}
          </text>
          <text x={Math.max(margin.left + 300, width - 260)} y={38} className="fill-muted-foreground text-[11px]">
            Min {Number.isFinite(minCoverage) ? minCoverage.toFixed(1) : "-"}X • Avg {Number.isFinite(avgCoverage) ? avgCoverage.toFixed(1) : "-"}X
          </text>

          <line x1={x(safeStart)} y1={144} x2={x(safeEnd)} y2={144} stroke="currentColor" strokeWidth="1" />
          <line x1={x(safeStart)} y1={136} x2={x(safeStart)} y2={152} stroke="currentColor" strokeWidth="1" />
          <line x1={x(safeEnd)} y1={136} x2={x(safeEnd)} y2={152} stroke="currentColor" strokeWidth="1" />
          <text x={x(safeStart)} y={171} className="fill-muted-foreground text-[10px]" textAnchor="start">
            {metric(safeStart)}
          </text>
          <text x={x(safeEnd)} y={171} className="fill-muted-foreground text-[10px]" textAnchor="end">
            {metric(safeEnd)}
          </text>

          {exons.map((row: any, index: number) => {
            const rectX = x(row.start)
            const rectWidth = Math.max(1, x(row.end) - x(row.start))
            const label = row.nbr || row.exon || index + 1
            return (
              <g key={`exon-${index}`}>
                <rect x={rectX} y={134} width={rectWidth} height={20} fill="#d1d5db">
                  <title>{coord(row)} exon {label}, cov {Number(row.cov).toFixed(2)}X</title>
                </rect>
                {rectWidth > 18 && (
                  <text x={rectX + rectWidth / 2} y={148} textAnchor="middle" className="fill-gray-900 text-[9px] font-bold">
                    {label}
                  </text>
                )}
              </g>
            )
          })}
          {cds.map((row: any, index: number) => {
            const cov = coverageNumber(row)
            const fill = Number.isNaN(cov) ? "#111827" : cov < cutoff ? "#fda4af" : "#86efac"
            const rectX = x(row.start)
            const rectWidth = Math.max(1, x(row.end) - x(row.start))
            const label = row.nbr || row.exon || index + 1
            return (
              <g key={`cds-${index}`}>
                <rect x={rectX} y={134} width={rectWidth} height={20} fill={fill}>
                  <title>{coord(row)} exon {label}, cov {Number.isNaN(cov) ? "N/A" : cov.toFixed(2)}X</title>
                </rect>
                {rectWidth > 42 && (
                  <text x={rectX + rectWidth / 2} y={130} textAnchor="middle" className={`${cov < cutoff ? "fill-fail" : "fill-pass"} text-[9px] font-bold`}>
                    {Number.isNaN(cov) ? "N/A" : `${cov.toFixed(0)}X`}
                  </text>
                )}
              </g>
            )
          })}
          {probes.map((row: any, index: number) => {
            const cov = coverageNumber(row)
            const rectX = x(row.start)
            const rectWidth = Math.max(1, x(row.end) - x(row.start))
            return (
              <g key={`probe-${index}`}>
                <rect x={rectX} y={95} width={rectWidth} height={18} fill={cov < cutoff ? "#fda4af" : "#93c5fd"}>
                  <title>{coord(row)}, cov {Number.isNaN(cov) ? "N/A" : cov.toFixed(2)}X</title>
                </rect>
                {rectWidth > 44 && (
                  <text x={rectX + rectWidth / 2} y={90} textAnchor="middle" className={`${cov < cutoff ? "fill-fail" : "fill-blue-700"} text-[9px] font-bold`}>
                    {Number.isNaN(cov) ? "N/A" : `${cov.toFixed(0)}X`}
                  </text>
                )}
              </g>
            )
          })}
          <text x={10} y={108} className="fill-muted-foreground text-[11px]">Probes</text>
          <text x={10} y={148} className="fill-muted-foreground text-[11px]">CDS/exons</text>
          <text x={10} y={190} className="fill-muted-foreground text-[10px]">Hover regions for exact coordinates and coverage.</text>
        </svg>
      </div>

      <div className="mt-2 flex flex-wrap gap-3 rounded-lg border border-border bg-background/70 px-3 py-2 text-xs">
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#fda4af]" /> Any coverage &lt; {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#93c5fd]" /> Probe coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#86efac]" /> CDS coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-[#111827]" /> Not covered by design</span>
      </div>

      <div className="mt-3 rounded-xl border border-emerald-200 border-t-4 border-t-emerald-500 bg-emerald-50/30 p-3 dark:bg-emerald-950/10">
        <div className="mb-3 flex gap-2 border-b border-border pb-2">
          <button
            onClick={() => setActiveTab("exons")}
            className={`rounded-md border px-2.5 py-1 text-xs font-bold ${activeTab === "exons" ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted"}`}
          >
            Exons ({lowExons.length})
          </button>
          <button
            onClick={() => setActiveTab("probes")}
            className={`rounded-md border px-2.5 py-1 text-xs font-bold ${activeTab === "probes" ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted"}`}
          >
            Probes ({lowProbes.length})
          </button>
        </div>
        {activeTab === "exons" ? renderRows(lowExons, "CDS") : renderRows(lowProbes, "probe")}
      </div>

      <div className="mt-3 rounded-xl border border-panel/20 border-t-4 border-t-panel bg-card/80 p-3 shadow-sm">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
          <div>
            <h4 className="text-sm font-black uppercase tracking-wide">Complete Gene Information</h4>
            <p className="text-xs text-muted-foreground">
              Full transcript, exon, CDS, and probe details from the coverage payload.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Exons</p>
              <p className="text-lg font-black">{exons.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">CDS</p>
              <p className="text-lg font-black">{cds.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Probes</p>
              <p className="text-lg font-black">{probes.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Min / Avg</p>
              <p className="text-sm font-black">
                {Number.isFinite(minCoverage) ? minCoverage.toFixed(1) : "-"} / {Number.isFinite(avgCoverage) ? avgCoverage.toFixed(1) : "-"}X
              </p>
            </div>
          </div>
        </div>

        <div className="mb-3 flex flex-wrap gap-2">
          {(["transcript", "exons", "cds", "probes"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setInfoTab(tab)}
              className={`rounded-md border px-2.5 py-1 text-xs font-bold capitalize ${infoTab === tab ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted"}`}
            >
              {tab === "cds" ? "CDS" : tab} {tab === "exons" ? `(${exons.length})` : tab === "cds" ? `(${cds.length})` : tab === "probes" ? `(${probes.length})` : ""}
            </button>
          ))}
        </div>

        {infoTab === "transcript" && (
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Coordinates</p>
              <p className="font-mono font-semibold">{transcript.chr || transcript.chrom || "-"}:{metric(transcript.start)}-{metric(transcript.end)}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Length</p>
              <p className="font-mono font-semibold">{metric(regionLength(transcript))} bp</p>
            </div>
            {transcriptRows.map(([key, value]) => (
              <div key={key} className="rounded-lg border border-border bg-background/70 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="break-words font-mono text-xs font-semibold">{String(value)}</p>
              </div>
            ))}
            {!transcriptRows.length && <p className="text-sm text-muted-foreground">No transcript metadata available.</p>}
          </div>
        )}
        {infoTab === "exons" && renderAllFeatureRows(exons, "exon")}
        {infoTab === "cds" && renderAllFeatureRows(cds, "CDS")}
        {infoTab === "probes" && renderAllFeatureRows(probes, "probe")}
      </div>
    </section>
  )
}

export function CoverageTab({ sampleId }: { sampleId: string }) {
  const [cutoff, setCutoff] = useState(500)
  const [selectedGene, setSelectedGene] = useState<string | null>(null)
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-coverage", sampleId, cutoff],
    queryFn: () => api.get(`/coverage/samples/${sampleId}?cov_cutoff=${cutoff}`).then((res) => res.data),
    retry: false,
  })

  const rows = useMemo(() => flattenCoverageTable(data?.cov_table), [data])
  const coveredGenes = Object.keys(data?.coverage?.genes || {}).length
  const geneNames = useMemo(() => Object.keys(data?.coverage?.genes || {}).sort(), [data])
  const geneSummaries = useMemo(() => {
    return geneNames.map((gene) => {
      const geneRows = rows.filter((row) => row.gene === gene)
      const values = geneRows.map((row) => coverageNumber(row)).filter(Number.isFinite)
      const min = values.length ? Math.min(...values) : Number.NaN
      return { gene, count: geneRows.length, min }
    })
  }, [geneNames, rows])
  const selectedGeneData = selectedGene ? data?.coverage?.genes?.[selectedGene] : null
  const selectedRows = selectedGene ? rows.filter((row) => row.gene === selectedGene) : rows

  useEffect(() => {
    if (!geneNames.length) {
      setSelectedGene(null)
      return
    }
    setSelectedGene((current) => current && geneNames.includes(current) ? current : geneNames[0])
  }, [geneNames])

  const columns: ColumnDef<any, any>[] = [
    {
      id: "gene",
      header: "Gene",
      accessorFn: (row) => row.gene,
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => setSelectedGene(row.original.gene)}
          className="font-bold text-primary underline-offset-2 hover:underline"
        >
          {row.original.gene}
        </button>
      ),
    },
    {
      id: "region",
      header: "Region",
      accessorFn: (row) => row.region || row.nbr || "-",
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.region || row.original.nbr || "-"}</span>,
    },
    {
      id: "chrom",
      header: "Chrom",
      accessorFn: (row) => row.chrom || row.chr || "-",
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.chrom || row.original.chr || "-"}</span>,
    },
    {
      id: "start",
      header: "Start",
      accessorFn: (row) => Number(row.start || 0),
      cell: ({ row }) => <span className="font-mono text-xs">{metric(row.original.start)}</span>,
    },
    {
      id: "end",
      header: "End",
      accessorFn: (row) => Number(row.end || 0),
      cell: ({ row }) => <span className="font-mono text-xs">{metric(row.original.end)}</span>,
    },
    {
      id: "coverage",
      header: "Coverage",
      accessorFn: (row) => Number(row.cov || 0),
      cell: ({ row }) => {
        const value = Number(row.original.cov)
        return (
          <span className={`font-mono text-xs font-bold ${Number.isFinite(value) && value < cutoff ? "text-fail" : "text-pass"}`}>
            {Number.isFinite(value) ? value.toFixed(1) : "-"}
          </span>
        )
      },
    },
    {
      id: "exon",
      header: "Exon",
      accessorFn: (row) => row.exon || row.exon_nr || row.nbr || "-",
      cell: ({ row }) => {
        const value = row.original.exon_nr || row.original.exon || row.original.nbr
        return <span className="text-xs">{Array.isArray(value) ? value.map((item: any) => item.nbr || item).join(", ") : value || "-"}</span>
      },
    },
  ]

  if (isLoading) return <div className="flex justify-center p-8"><Activity className="animate-spin text-muted-foreground" /></div>
  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertTriangle className="mr-2 inline h-4 w-4" />
        {error instanceof Error ? error.message : "Error loading coverage"}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <SurfacePanel
        title="Coverage"
        description="Low-covered genes, exon/CDS/probe coverage, and blacklist controls for the active sample gene lists."
        actions={
          <label className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
            Cutoff
            <input
              type="number"
              min={1}
              value={cutoff}
              onChange={(event) => setCutoff(Number(event.target.value) || 1)}
              className="w-20 rounded-lg border border-input bg-background px-2 py-1 text-xs font-semibold text-foreground"
            />
          </label>
        }
      >
        <div className="grid gap-2 sm:grid-cols-3">
          <MetricCard title="Low regions" value={shortCount(rows.length)} />
          <MetricCard title="Genes with coverage" value={shortCount(coveredGenes)} />
          <MetricCard title="Assay group" value={data?.smp_grp || "-"} className="uppercase" />
        </div>
      </SurfacePanel>

      <div className="coverage-split-layout flex flex-col gap-3 md:flex-row">
        <aside className="coverage-sidebar space-y-3">
          <SurfacePanel title="Low-Coverage Genes" description={`${geneNames.length} gene(s) below ${cutoff}X`}>
            <div className="max-h-[28rem] space-y-1 overflow-y-auto pr-1">
              {geneSummaries.map((item) => (
                <button
                  key={item.gene}
                  type="button"
                  onClick={() => setSelectedGene(item.gene)}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                    selectedGene === item.gene
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background/70 hover:bg-muted"
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-black">{item.gene}</span>
                    <span className="text-[10px] text-muted-foreground">{item.count} low region(s)</span>
                  </span>
                  <span className="rounded-md bg-fail/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-fail">
                    {Number.isFinite(item.min) ? `${item.min.toFixed(1)}X` : "-"}
                  </span>
                </button>
              ))}
              {!geneSummaries.length && (
                <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No low-covered genes for the current cutoff and selected gene lists.
                </p>
              )}
            </div>
          </SurfacePanel>

          <SurfacePanel title="Low Regions">
            <DataTable columns={columns} data={selectedRows} filename={`coverage_${sampleId}.csv`} />
          </SurfacePanel>
        </aside>

        <div className="coverage-main flex-1 space-y-3">
          {selectedGene && selectedGeneData ? (
            <CoverageGeneView gene={selectedGene} geneData={selectedGeneData} cutoff={cutoff} smpGrp={data?.smp_grp || ""} />
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-card/60 px-4 py-8 text-center text-sm text-muted-foreground">
              Select a gene from the low-coverage list to inspect transcript coverage, exons, probes, and blacklist low regions.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
