// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Badge } from "@/components/ui/badge"
import { Surface } from "@/components/ui/surface"
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table"
import { MetricCard } from "@/components/cards/Panel"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { icon } from "@/lib/assets"
import { useState } from "react"
import { coord, coverageNumber, metric, regionLength, type CoverageFeatureKind, type InspectedCoverageFeature } from "./coverage-presentation"

export function CoverageGeneView({
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
  const queryClient = useQueryClient()
  const access = useCurrentUserAccess()
  const canManage = hasPermission(access.data, "coverage.blacklist:manage")
  const [zoom, setZoom] = useState(1)
  const [activeTab, setActiveTab] = useState<"exons" | "probes">("exons")
  const [infoTab, setInfoTab] = useState<"transcript" | "exons" | "cds" | "probes">("transcript")
  const [inspection, setInspection] = useState<{ gene: string; data: unknown; feature: InspectedCoverageFeature } | null>(null)
  const inspectedFeature = inspection?.gene === gene && inspection.data === geneData ? inspection.feature : null
  const transcript = geneData?.transcript || {}
  const exons = Array.isArray(geneData?.exons) ? geneData.exons : []
  const cds = Array.isArray(geneData?.CDS) ? geneData.CDS : []
  const probes = Array.isArray(geneData?.probes) ? geneData.probes : []
  const lowExons = cds.filter((row: any) => !row.blacklisted && coverageNumber(row) < cutoff)
  const lowProbes = probes.filter((row: any) => !row.blacklisted && coverageNumber(row) < cutoff)
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
    setInspection({ gene, data: geneData, feature: {
      kind,
      label: String(row.nbr || row.exon || row.name || row.id || `${kind} ${index + 1}`),
      coordinates: coord(row),
      coverage: coverageNumber(row),
      length: regionLength(row),
    } })
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
      void queryClient.invalidateQueries({ queryKey: ["sample-coverage"] })
      void queryClient.invalidateQueries({ queryKey: ["coverage-blacklisted"] })
      notifySuccess("Coverage region blacklisted", `${gene} ${variables.region} was added to the blacklist.`, "Coverage")
    },
    onError: (error) => {
      notifyActionError("Unable to blacklist coverage region", error, "Coverage")
    },
  })

  const renderRows = (rows: any[], region: "CDS" | "probe") => (
    <div className="table-frame max-h-72 overflow-auto">
      <Table>
        <TableHeader className="sticky top-0">
          <TableRow>
            {region === "CDS" && <TableHead>Exon</TableHead>}
            <TableHead>Coordinates</TableHead>
            <TableHead>Coverage</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={`${coord(row)}-${index}`}>
              {region === "CDS" && <TableCell>{row.nbr || row.exon || "-"}</TableCell>}
              <TableCell>{coord(row)}</TableCell>
              <TableCell className="font-bold text-fail">{coverageNumber(row).toFixed(2)}X</TableCell>
              <TableCell>{metric(regionLength(row))}</TableCell>
              <TableCell>
                {canManage && <button
                  onClick={() => blacklist.mutate({ row, region })}
                  disabled={blacklist.isPending}
                  className="rounded-md border border-fail/30 bg-fail/10 px-2 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
                >
                  Blacklist
                </button>}
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && (
            <TableRow>
              <TableCell colSpan={region === "CDS" ? 5 : 4} className="py-6 text-center text-muted-foreground">
                No low-coverage {region === "CDS" ? "exons" : "probes"} below {cutoff}X.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
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
    <div className="table-frame max-h-96 overflow-auto">
      <Table>
        <TableHeader className="sticky top-0">
          <TableRow>
            <TableHead>Feature</TableHead>
            <TableHead>Coordinates</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Coverage</TableHead>
            <TableHead>Status</TableHead>
            {region === "probe" && <TableHead>Overlapping exons</TableHead>}
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row: any, index: number) => {
            const cov = coverageNumber(row)
            const isLow = Number.isFinite(cov) && cov < cutoff
            const featureLabel = row.nbr || row.exon || row.name || row.id || `${region} ${index + 1}`
            const overlapping = Array.isArray(row.exon_nr)
              ? row.exon_nr.map((item: any) => item.nbr || item.exon || item).join(", ")
              : row.exon_nr || "-"
            return (
              <TableRow key={`${region}-${coord(row)}-${index}`}>
                <TableCell>{featureLabel}</TableCell>
                <TableCell>{coord(row)}</TableCell>
                <TableCell>{metric(regionLength(row))}</TableCell>
                <TableCell className={`px-2 py-1 font-bold ${isLow ? "text-fail" : "text-pass"}`}>
                  {Number.isFinite(cov) ? `${cov.toFixed(2)}X` : "N/A"}
                </TableCell>
                <TableCell>
                  <span className={`rounded-md px-2 py-1 type-label font-bold uppercase ${isLow ? "bg-fail/10 text-fail" : "bg-pass/10 text-pass"}`}>
                    {row.blacklisted ? "Blacklisted" : Number.isFinite(cov) ? (isLow ? "Low" : "Pass") : "No design"}
                  </span>
                </TableCell>
                {region === "probe" && <TableCell>{overlapping}</TableCell>}
                <TableCell>
                  {canManage && !row.blacklisted && (region === "CDS" || region === "probe") && (
                    <button
                      onClick={() => blacklist.mutate({ row, region })}
                      disabled={blacklist.isPending}
                      className="rounded-md border border-fail/30 bg-fail/10 px-2 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
                    >
                      Blacklist
                    </button>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
          {!rows.length && (
            <TableRow>
              <TableCell colSpan={region === "probe" ? 7 : 6} className="py-6 text-center text-muted-foreground">
                No {region} data available for this gene.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )

  return (
    <Surface as="section" variant="card" className="min-w-0 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
        <div className="min-w-0">
          <h3 className="type-section-title">{gene} coverage</h3>
          <p className="type-meta text-muted-foreground">
            {transcriptChr}:{metric(safeStart)}-{metric(safeEnd)} · {metric(transcriptLength)} bp · cutoff {cutoff}X
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AppTooltip content="Reduce the genomic track scale.">
            <button aria-label="Zoom out" className="soft-icon-button" onClick={() => setZoom((value) => Math.max(0.5, value / 1.25))}><icon.zoomOut className="h-4 w-4" /></button>
          </AppTooltip>
          <AppTooltip content="Increase the genomic track scale and use the horizontal scrollbar to inspect the complete interval.">
            <button aria-label="Zoom in" className="soft-icon-button" onClick={() => setZoom((value) => Math.min(8, value * 1.25))}><icon.zoomIn className="h-4 w-4" /></button>
          </AppTooltip>
          <AppTooltip content="Return the genomic track to its original scale.">
            <button aria-label="Reset zoom" className="soft-icon-button" onClick={() => setZoom(1)}><icon.rotateCcw className="h-4 w-4" /></button>
          </AppTooltip>
          <Badge variant="outline" className="border-border bg-background">{Math.round(zoom * 100)}%</Badge>
          {canManage && <button
            onClick={() => blacklist.mutate({ region: "" })}
            disabled={blacklist.isPending}
            className="rounded-md border border-fail/30 bg-fail/10 px-2.5 py-1 text-xs font-bold text-fail hover:bg-fail/20 disabled:opacity-50"
          >
            Blacklist gene
          </button>}
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

      <Surface variant="inset"
        className="max-w-full overflow-x-auto overscroll-x-contain  p-2"
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
      </Surface>

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

      <Surface variant="inset" className="mt-2 flex flex-wrap gap-3  px-3 py-2 text-xs">
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-low h-3 w-3 rounded-sm" /> Any coverage &lt; {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-probe h-3 w-3 rounded-sm" /> Probe coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-cds h-3 w-3 rounded-sm" /> CDS coverage &gt;= {cutoff}</span>
        <span className="inline-flex items-center gap-2"><span className="coverage-swatch-unavailable h-3 w-3 rounded-sm" /> Not covered by design</span>
      </Surface>

      <Surface variant="card" className="mt-3 p-3">
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
      </Surface>

      <Surface variant="card" className="mt-3 border-panel/20 p-3">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wide">Complete Gene Information</h4>
            <p className="text-xs text-muted-foreground">
              Full transcript, exon, CDS, and probe details from the coverage payload.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <Surface variant="inset" className="px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Exons</p>
              <p className="text-lg font-semibold">{exons.length}</p>
            </Surface>
            <Surface variant="inset" className="px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">CDS</p>
              <p className="text-lg font-semibold">{cds.length}</p>
            </Surface>
            <Surface variant="inset" className="px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Probes</p>
              <p className="text-lg font-semibold">{probes.length}</p>
            </Surface>
            <Surface variant="inset" className="px-3 py-2">
              <p className="font-bold uppercase text-muted-foreground">Min / Avg</p>
              <p className="text-sm font-semibold">
                {Number.isFinite(minCoverage) ? minCoverage.toFixed(1) : "-"} / {Number.isFinite(avgCoverage) ? avgCoverage.toFixed(1) : "-"}X
              </p>
            </Surface>
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
            <Surface variant="inset" className="px-3 py-2">
              <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">Coordinates</p>
              <p className="font-semibold">{transcript.chr || transcript.chrom || "-"}:{metric(transcript.start)}-{metric(transcript.end)}</p>
            </Surface>
            <Surface variant="inset" className="px-3 py-2">
              <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">Length</p>
              <p className="font-semibold">{metric(regionLength(transcript))} bp</p>
            </Surface>
            {transcriptRows.map(([key, value]) => (
              <Surface variant="inset" key={key} className="px-3 py-2">
                <p className="type-label font-semibold uppercase tracking-wider text-muted-foreground">{key.replaceAll("_", " ")}</p>
                <p className="break-words text-xs font-semibold">{String(value)}</p>
              </Surface>
            ))}
            {!transcriptRows.length && <p className="text-sm text-muted-foreground">No transcript metadata available.</p>}
          </div>
        )}
        {infoTab === "exons" && renderAllFeatureRows(exons, "exon")}
        {infoTab === "cds" && renderAllFeatureRows(cds, "CDS")}
        {infoTab === "probes" && renderAllFeatureRows(probes, "probe")}
      </Surface>
    </Surface>
  )
}
