import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { AlertTriangle, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { Input } from "@/components/ui/input"
import { shortCount } from "@/lib/detail-formatters"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { sampleFilterSection } from "@/lib/sample-shape"

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

type CoverageFeatureKind = "Probe" | "Exon" | "CDS"

type InspectedCoverageFeature = {
  kind: CoverageFeatureKind
  label: string
  coordinates: string
  coverage: number
  length: number
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
  const [inspectedFeature, setInspectedFeature] = useState<InspectedCoverageFeature | null>(null)
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
  const width = Math.max(920, Math.round(1100 * zoom))
  const height = 250
  const margin = { left: 112, right: 32 }
  const trackY = { probes: 48, exons: 98, cds: 146, ruler: 205 }
  const transcriptChr = transcript.chr || transcript.chrom || exons[0]?.chr || cds[0]?.chr || probes[0]?.chr || "-"
  const transcriptLength = safeEnd - safeStart
  const x = (value: unknown) => {
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return margin.left
    return margin.left + ((numeric - safeStart) / (safeEnd - safeStart)) * (width - margin.left - margin.right)
  }
  const ticks = Array.from({ length: 6 }, (_, index) => safeStart + ((safeEnd - safeStart) * index) / 5)
  const inspectFeature = (kind: CoverageFeatureKind, row: any, index: number) => {
    setInspectedFeature({
      kind,
      label: String(row.nbr || row.exon || row.name || row.id || `${kind} ${index + 1}`),
      coordinates: coord(row),
      coverage: coverageNumber(row),
      length: regionLength(row),
    })
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
      <table className="type-table-cell w-full text-left">
        <thead className="type-table-header sticky top-0 bg-muted text-muted-foreground">
          <tr>
            {region === "CDS" && <th className="px-2 py-1">Exon</th>}
            <th className="px-2 py-1">Coordinates</th>
            <th className="px-2 py-1">Coverage</th>
            <th className="px-2 py-1">Size</th>
            <th className="px-2 py-1">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${coord(row)}-${index}`} className="border-t border-border/40">
              {region === "CDS" && <td className="px-2 py-1 ">{row.nbr || row.exon || "-"}</td>}
              <td className="px-2 py-1 ">{coord(row)}</td>
              <td className="px-2 py-1 font-bold text-fail">{coverageNumber(row).toFixed(2)}X</td>
              <td className="px-2 py-1 ">{metric(regionLength(row))}</td>
              <td className="px-2 py-1">
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
      <table className="type-table-cell w-full text-left">
        <thead className="type-table-header sticky top-0 bg-muted text-muted-foreground">
          <tr>
            <th className="px-2 py-1">Feature</th>
            <th className="px-2 py-1">Coordinates</th>
            <th className="px-2 py-1">Size</th>
            <th className="px-2 py-1">Coverage</th>
            <th className="px-2 py-1">Status</th>
            {region === "probe" && <th className="px-2 py-1">Overlapping exons</th>}
            <th className="px-2 py-1">Actions</th>
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
              <tr key={`${region}-${coord(row)}-${index}`} className="border-t border-border/40">
                <td className="px-2 py-1 ">{featureLabel}</td>
                <td className="px-2 py-1 ">{coord(row)}</td>
                <td className="px-2 py-1 ">{metric(regionLength(row))}</td>
                <td className={`px-2 py-1 font-bold ${isLow ? "text-fail" : "text-pass"}`}>
                  {Number.isFinite(cov) ? `${cov.toFixed(2)}X` : "N/A"}
                </td>
                <td className="px-2 py-1">
                  <span className={`rounded-md px-2 py-1 type-label font-bold uppercase ${isLow ? "bg-fail/10 text-fail" : "bg-pass/10 text-pass"}`}>
                    {Number.isFinite(cov) ? (isLow ? "Low" : "Pass") : "No design"}
                  </span>
                </td>
                {region === "probe" && <td className="px-2 py-1 ">{overlapping}</td>}
                <td className="px-2 py-1">
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
    <section className="glass-card min-w-0 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
        <div className="min-w-0">
          <h3 className="type-section-title">{gene} coverage</h3>
          <p className="type-meta text-muted-foreground">
            {transcriptChr}:{metric(safeStart)}-{metric(safeEnd)} · {metric(transcriptLength)} bp · cutoff {cutoff}X
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AppTooltip content="Reduce the genomic track scale.">
            <button aria-label="Zoom out" className="soft-icon-button" onClick={() => setZoom((value) => Math.max(0.5, value / 1.25))}><ZoomOut className="h-4 w-4" /></button>
          </AppTooltip>
          <AppTooltip content="Increase the genomic track scale and use the horizontal scrollbar to inspect the complete interval.">
            <button aria-label="Zoom in" className="soft-icon-button" onClick={() => setZoom((value) => Math.min(8, value * 1.25))}><ZoomIn className="h-4 w-4" /></button>
          </AppTooltip>
          <AppTooltip content="Return the genomic track to its original scale.">
            <button aria-label="Reset zoom" className="soft-icon-button" onClick={() => setZoom(1)}><RotateCcw className="h-4 w-4" /></button>
          </AppTooltip>
          <span className="type-badge rounded-md border border-border bg-background px-2 py-1">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => blacklist.mutate({ region: "" })}
            disabled={blacklist.isPending}
            className="rounded-md border border-fail/30 bg-fail/10 px-2.5 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
          >
            Blacklist gene
          </button>
        </div>
      </div>

      <div className="mb-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard title="Exons" value={metric(exons.length)} />
        <MetricCard title="CDS regions" value={metric(cds.length)} />
        <MetricCard title="Probes" value={metric(probes.length)} />
        <MetricCard
          title="Minimum / mean"
          value={`${Number.isFinite(minCoverage) ? minCoverage.toFixed(1) : "-"} / ${Number.isFinite(avgCoverage) ? avgCoverage.toFixed(1) : "-"}X`}
        />
      </div>

      <div
        className="max-w-full overflow-x-auto overscroll-x-contain rounded-lg border border-border bg-background p-2"
        role="region"
        aria-label={`${gene} coverage plot viewport`}
        tabIndex={0}
      >
        <svg
          className="block max-w-none shrink-0"
          width={width}
          height={height}
          role="img"
          aria-label={`${gene} coverage plot`}
        >
          {ticks.map((tick, index) => (
            <g key={`tick-${index}`}>
              <line x1={x(tick)} y1={26} x2={x(tick)} y2={trackY.ruler} className="stroke-border" strokeDasharray="3 5" />
              <line x1={x(tick)} y1={trackY.ruler} x2={x(tick)} y2={trackY.ruler + 7} className="stroke-muted-foreground" />
              <text
                x={x(tick)}
                y={trackY.ruler + 23}
                textAnchor={index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}
                className="fill-muted-foreground type-label"
              >
                {metric(Math.round(tick))}
              </text>
            </g>
          ))}
          <line x1={x(safeStart)} y1={trackY.ruler} x2={x(safeEnd)} y2={trackY.ruler} className="stroke-muted-foreground" />
          <text x={margin.left - 14} y={trackY.probes + 14} textAnchor="end" className="fill-foreground type-meta">Probes</text>
          <text x={margin.left - 14} y={trackY.exons + 15} textAnchor="end" className="fill-foreground type-meta">Exon design</text>
          <text x={margin.left - 14} y={trackY.cds + 15} textAnchor="end" className="fill-foreground type-meta">CDS coverage</text>
          <text x={margin.left - 14} y={trackY.ruler + 4} textAnchor="end" className="fill-muted-foreground type-label">Position</text>

          {exons.map((row: any, index: number) => {
            const rectX = x(row.start)
            const rectWidth = Math.max(1, x(row.end) - x(row.start))
            const label = row.nbr || row.exon || index + 1
            return (
              <g key={`exon-${index}`}>
                <rect
                  x={rectX} y={trackY.exons} width={rectWidth} height={24} rx={2}
                  fill="var(--coverage-exon)" tabIndex={0} role="button"
                  aria-label={`Exon ${label}, ${coord(row)}`}
                  onMouseEnter={() => inspectFeature("Exon", row, index)}
                  onFocus={() => inspectFeature("Exon", row, index)}
                />
                {rectWidth > 18 && (
                  <text x={rectX + rectWidth / 2} y={trackY.exons + 16} textAnchor="middle" className="pointer-events-none fill-foreground type-label font-semibold">
                    {label}
                  </text>
                )}
              </g>
            )
          })}
          {cds.map((row: any, index: number) => {
            const cov = coverageNumber(row)
            const fill = Number.isNaN(cov) ? "var(--coverage-unavailable)" : cov < cutoff ? "var(--coverage-low)" : "var(--coverage-cds)"
            const rectX = x(row.start)
            const rectWidth = Math.max(1, x(row.end) - x(row.start))
            const label = row.nbr || row.exon || index + 1
            return (
              <g key={`cds-${index}`}>
                <rect
                  x={rectX} y={trackY.cds} width={rectWidth} height={24} rx={2}
                  fill={fill} tabIndex={0} role="button"
                  aria-label={`CDS ${label}, ${coord(row)}, ${Number.isNaN(cov) ? "no coverage" : `${cov.toFixed(2)}X`}`}
                  onMouseEnter={() => inspectFeature("CDS", row, index)}
                  onFocus={() => inspectFeature("CDS", row, index)}
                />
                {rectWidth > 42 && (
                  <text x={rectX + rectWidth / 2} y={trackY.cds - 5} textAnchor="middle" className={`${cov < cutoff ? "fill-fail" : "fill-pass"} pointer-events-none type-label font-semibold`}>
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
                <rect
                  x={rectX} y={trackY.probes} width={rectWidth} height={22} rx={2}
                  fill={Number.isNaN(cov) ? "var(--coverage-unavailable)" : cov < cutoff ? "var(--coverage-low)" : "var(--coverage-probe)"}
                  tabIndex={0} role="button"
                  aria-label={`Probe ${index + 1}, ${coord(row)}, ${Number.isNaN(cov) ? "no coverage" : `${cov.toFixed(2)}X`}`}
                  onMouseEnter={() => inspectFeature("Probe", row, index)}
                  onFocus={() => inspectFeature("Probe", row, index)}
                />
                {rectWidth > 44 && (
                  <text x={rectX + rectWidth / 2} y={trackY.probes - 5} textAnchor="middle" className={`${cov < cutoff ? "fill-fail" : "fill-tier3"} pointer-events-none type-label font-semibold`}>
                    {Number.isNaN(cov) ? "N/A" : `${cov.toFixed(0)}X`}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>

      <div className="mt-2 min-h-14 rounded-lg border border-border bg-muted/40 px-3 py-2" aria-live="polite">
        {inspectedFeature ? (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
            <div><p className="type-label text-muted-foreground">Feature</p><p className="type-body-sm font-semibold">{inspectedFeature.kind} {inspectedFeature.label}</p></div>
            <div><p className="type-label text-muted-foreground">Coordinates</p><p className="type-body-sm">{inspectedFeature.coordinates}</p></div>
            <div><p className="type-label text-muted-foreground">Length</p><p className="type-body-sm">{metric(inspectedFeature.length)} bp</p></div>
            <div>
              <p className="type-label text-muted-foreground">Coverage</p>
              <p className={`type-body-sm font-semibold ${Number.isFinite(inspectedFeature.coverage) && inspectedFeature.coverage < cutoff ? "text-fail" : "text-pass"}`}>
                {Number.isFinite(inspectedFeature.coverage) ? `${inspectedFeature.coverage.toFixed(2)}X` : "Not measured"}
              </p>
            </div>
          </div>
        ) : (
          <p className="type-body-sm text-muted-foreground">Hover over or focus a probe, exon, or CDS region to inspect its coordinates and coverage.</p>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-3 rounded-lg border border-border bg-background/70 px-3 py-2 text-xs">
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-low h-3 w-3 rounded-sm" /> Any coverage &lt; {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-probe h-3 w-3 rounded-sm" /> Probe coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-cds h-3 w-3 rounded-sm" /> CDS coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-unavailable h-3 w-3 rounded-sm" /> Not covered by design</span>
      </div>

      <div className="glass-card mt-3 p-3">
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

      <div className="glass-card mt-3 border-panel/20 p-3">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wide">Complete Gene Information</h4>
            <p className="text-xs text-muted-foreground">
              Full transcript, exon, CDS, and probe details from the coverage payload.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Exons</p>
              <p className="text-lg font-semibold">{exons.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">CDS</p>
              <p className="text-lg font-semibold">{cds.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Probes</p>
              <p className="text-lg font-semibold">{probes.length}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Min / Avg</p>
              <p className="text-sm font-semibold">
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
              <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">Coordinates</p>
              <p className="font-semibold">{transcript.chr || transcript.chrom || "-"}:{metric(transcript.start)}-{metric(transcript.end)}</p>
            </div>
            <div className="rounded-lg border border-border bg-background/70 px-3 py-2">
              <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">Length</p>
              <p className="font-semibold">{metric(regionLength(transcript))} bp</p>
            </div>
            {transcriptRows.map(([key, value]) => (
              <div key={key} className="rounded-lg border border-border bg-background/70 px-3 py-2">
                <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="break-words text-xs font-semibold">{String(value)}</p>
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

export function CoverageTab({ sampleId, sample }: { sampleId: string; sample?: any }) {
  const configuredCutoff = Number(sampleFilterSection(sample, "coverage").warn_cov)
  const cutoff = Number.isFinite(configuredCutoff) && configuredCutoff > 0 ? configuredCutoff : 500
  const [selectedGene, setSelectedGene] = useState<string | null>(null)
  const [geneSearch, setGeneSearch] = useState("")
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-coverage", sampleId, cutoff],
    queryFn: () => api.get(`/samples/${sampleId}/coverage?cov_cutoff=${cutoff}`).then((res) => res.data),
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
  const filteredGeneSummaries = useMemo(() => {
    const query = geneSearch.trim().toLowerCase()
    if (!query) return geneSummaries
    return geneSummaries.filter((item) => item.gene.toLowerCase().includes(query))
  }, [geneSearch, geneSummaries])
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
      cell: ({ row }) => <span className="text-xs">{row.original.region || row.original.nbr || "-"}</span>,
    },
    {
      id: "chrom",
      header: "Chrom",
      accessorFn: (row) => row.chrom || row.chr || "-",
      cell: ({ row }) => <span className="text-xs">{row.original.chrom || row.original.chr || "-"}</span>,
    },
    {
      id: "start",
      header: "Start",
      accessorFn: (row) => Number(row.start || 0),
      cell: ({ row }) => <span className="text-xs">{metric(row.original.start)}</span>,
    },
    {
      id: "end",
      header: "End",
      accessorFn: (row) => Number(row.end || 0),
      cell: ({ row }) => <span className="text-xs">{metric(row.original.end)}</span>,
    },
    {
      id: "coverage",
      header: "Coverage",
      accessorFn: (row) => Number(row.cov || 0),
      cell: ({ row }) => {
        const value = Number(row.original.cov)
        return (
          <span className={`text-xs font-bold ${Number.isFinite(value) && value < cutoff ? "text-fail" : "text-pass"}`}>
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

  if (isLoading) return <AppLoader label="Loading coverage" />
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
        description="Low-covered genes, exon/CDS/probe coverage, and blacklist controls for the active assay design."
      >
        <div className="grid gap-2 sm:grid-cols-3">
          <MetricCard title="Low regions" value={shortCount(rows.length)} />
          <MetricCard title="Genes with coverage" value={shortCount(coveredGenes)} />
          <MetricCard title="Assay group" value={data?.smp_grp || "-"} className="uppercase" />
        </div>
      </SurfacePanel>

      <div className="coverage-split-layout flex min-w-0 flex-col gap-3 md:flex-row">
        <aside className="coverage-sidebar min-w-0 space-y-3">
          <SurfacePanel
            title="Low-Coverage Genes"
            description={geneSearch.trim()
              ? `${filteredGeneSummaries.length} of ${geneNames.length} gene(s) below ${cutoff}X`
              : `${geneNames.length} gene(s) below ${cutoff}X`}
            actions={
              <div className="relative w-full sm:w-48">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  value={geneSearch}
                  onChange={(event) => setGeneSearch(event.target.value)}
                  placeholder="Search genes..."
                  aria-label="Search low-coverage genes"
                  className="h-8 pl-8 text-xs"
                />
              </div>
            }
          >
            <div className="max-h-[28rem] space-y-1 overflow-y-auto pr-1">
              {filteredGeneSummaries.map((item) => (
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
                    <span className="block truncate text-xs font-medium">{item.gene}</span>
                    <span className="type-label text-muted-foreground">{item.count} low region(s)</span>
                  </span>
                  <span className="rounded-md bg-fail/10 px-1.5 py-0.5 type-label font-bold text-fail">
                    {Number.isFinite(item.min) ? `${item.min.toFixed(1)}X` : "-"}
                  </span>
                </button>
              ))}
              {!geneSummaries.length && (
                <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No low-covered genes for the current cutoff and selected gene lists.
                </p>
              )}
              {geneSummaries.length > 0 && !filteredGeneSummaries.length && (
                <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No low-coverage genes match {geneSearch.trim()}.
                </p>
              )}
            </div>
          </SurfacePanel>

          <SurfacePanel title="Low Regions">
            <DataTable columns={columns} data={selectedRows} filename={`coverage_${sampleId}.csv`} />
          </SurfacePanel>
        </aside>

        <div className="coverage-main min-w-0 flex-1 space-y-3">
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
