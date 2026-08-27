import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, ArrowLeft, ExternalLink } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { TimeDisplay } from "@/components/ui/time-display"
import { TierBadge } from "@/lib/variant-ui"
import { displayValue } from "@/lib/detail-formatters"
import { sampleDetailPath } from "@/lib/sample-routing"

function selectedCsq(variant: any) {
  return variant?.INFO?.selected_CSQ || {}
}

function sampleName(row: any) {
  return row?.sample?.sample_name || row?.sample_name || row?.sample?.name || "-"
}

function sampleId(row: any) {
  return row?.sample?.name || row?.sample_name || row?.sample?.sample_name || row?.sample_id || row?.sample_oid || row?.sample?._id
}

function samplePayload(row: any) {
  return row?.sample || { name: row?.sample_name, sample_name: row?.sample_name, sample_id: row?.sample_id, sample_oid: row?.sample_oid }
}

export function TieredVariantContext() {
  const { variantId, tier } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ["tiered-variant-context", variantId, tier],
    queryFn: () => api.get(`/common/reported_variants/variant/${variantId}/${tier}`).then((res) => res.data),
    enabled: Boolean(variantId && tier),
  })

  if (isLoading) {
    return <AppLoader label="Loading reported variant" />
  }

  if (error || !data) {
    return (
      <PageShell eyebrow="Reported Variant" title="Unable to load tiered variant">
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error instanceof Error ? error.message : "The reported variant context could not be loaded."}
        </div>
      </PageShell>
    )
  }

  const variant = data.variant || {}
  const csq = selectedCsq(variant)
  const docs = data.docs || []
  const variantTier = Number(data.tier ?? tier)

  const columns: ColumnDef<any, any>[] = [
    {
      id: "sample",
      header: "Sample",
      accessorFn: sampleName,
      cell: ({ row }) => {
        const name = sampleName(row.original)
        const id = sampleId(row.original)
        return name === "-" ? (
          <span className="text-muted-foreground">-</span>
        ) : (
          <Link to={sampleDetailPath(samplePayload(row.original), id)} className="link-text font-bold">{name}</Link>
        )
      },
    },
    {
      id: "assay",
      header: "Assay",
      accessorFn: (row) => row?.annotation?.assay || row?.assay || row?.sample?.asp_id || "-",
      cell: ({ row }) => <span className="text-xs font-semibold uppercase">{String(row.getValue("assay"))}</span>,
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (row) => row?.annotation?.subpanel || row?.subpanel || row?.sample?.subpanel_id || "-",
    },
    {
      id: "report",
      header: "Report",
      accessorFn: (row) => row.report_id || row.report_num || row.report_oid || "-",
      cell: ({ row }) => {
        const id = sampleId(row.original)
        const reportId = row.original.report_id
        const label = row.original.report_num || reportId || row.original.report_oid || "-"
        return id && reportId ? (
          <Link to={`${sampleDetailPath(samplePayload(row.original), id)}/reports/${reportId}`} className="rounded-md bg-tier2 px-2 py-0.5 text-xs font-black text-white hover:bg-tier2/90">
            {String(label)}
          </Link>
        ) : <span>{String(label)}</span>
      },
    },
    {
      id: "reported_on",
      header: "Reported",
      accessorFn: (row) => row.reported_on || row.created_on || row.time_created || "-",
      cell: ({ row }) => <TimeDisplay value={row.getValue("reported_on")} mode="full" className="text-xs text-muted-foreground" />,
    },
    {
      id: "tier",
      header: "Tier",
      accessorFn: (row) => row.tier || row.class || 999,
      meta: { headerClassName: "w-14 min-w-14", cellClassName: "w-14 min-w-14" },
      cell: ({ row }) => <TierBadge tier={row.getValue("tier")} />,
    },
    {
      id: "gene",
      header: "Gene",
      accessorFn: (row) => row.gene || row.annotation?.gene || "-",
    },
    {
      id: "hgvs",
      header: "HGVS",
      accessorFn: (row) => [row.hgvsp, row.hgvsc].filter(Boolean).join(" ") || row.variant || "-",
      cell: ({ row }) => (
        <div className="flex max-w-md flex-col gap-0.5 text-xs">
          <span className="break-all font-semibold">{displayValue(row.original.hgvsp)}</span>
          <span className="break-all text-muted-foreground">{displayValue(row.original.hgvsc)}</span>
        </div>
      ),
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const id = sampleId(row.original)
        const varOid = row.original.var_oid || row.original.variant_oid
        return id && varOid ? (
          <Link to={`${sampleDetailPath(samplePayload(row.original), id)}/variant/${varOid}`} className="inline-flex rounded-md bg-primary/10 p-1.5 text-primary hover:bg-primary hover:text-white">
            <ExternalLink className="h-4 w-4" />
          </Link>
        ) : <span className="text-muted-foreground">-</span>
      },
    },
  ]

  return (
    <PageShell
      eyebrow="Reported Variant"
      title={`${csq.SYMBOL || "Unknown"} tier ${variantTier}`}
      description="Reported samples and reports matching this variant identity."
      actions={
        <Link to={sampleDetailPath(data.sample, variant.SAMPLE_ID || data.sample_id || "")} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-bold hover:bg-muted">
          <ArrowLeft className="h-4 w-4" />
          Back to sample
        </Link>
      }
    >
      {data.error && (
        <div className="rounded-xl border border-warn/30 bg-warn/10 p-4 text-sm font-semibold text-warn">
          {data.error}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-5">
        <section className="surface-panel p-3 lg:col-span-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Match Summary</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-background/70 p-3">
              <div className="text-xs text-muted-foreground">Matches</div>
              <div className="text-2xl font-black">{docs.length}</div>
            </div>
            <div className="rounded-xl border border-border bg-background/70 p-3">
              <div className="text-xs text-muted-foreground">Gene</div>
              <div className="text-lg font-black">{displayValue(csq.SYMBOL)}</div>
            </div>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Matching uses the gene and one available identity key: simple ID hash, simple ID, HGVSc, or HGVSp.
          </p>
        </section>

        <section className="surface-panel p-3 lg:col-span-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Variant Identity</h2>
          <dl className="mt-3 grid gap-2 text-xs">
            <div className="rounded-lg bg-background/70 p-2">
              <dt className="text-muted-foreground">Tier</dt>
              <dd><TierBadge tier={variantTier} /></dd>
            </div>
            <div className="rounded-lg bg-background/70 p-2">
              <dt className="text-muted-foreground">simple_id</dt>
              <dd className="break-all ">{displayValue(variant.simple_id)}</dd>
            </div>
            <div className="rounded-lg bg-background/70 p-2">
              <dt className="text-muted-foreground">simple_id_hash</dt>
              <dd className="break-all ">{displayValue(variant.simple_id_hash)}</dd>
            </div>
            <div className="rounded-lg bg-background/70 p-2">
              <dt className="text-muted-foreground">HGVSc</dt>
              <dd className="break-all ">{displayValue(csq.HGVSc)}</dd>
            </div>
            <div className="rounded-lg bg-background/70 p-2">
              <dt className="text-muted-foreground">HGVSp</dt>
              <dd className="break-all ">{displayValue(csq.HGVSp)}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="surface-panel p-3">
        <DataTable columns={columns} data={docs} rowLabel="reported matches" totalCount={docs.length} filename="reported_variant_matches.csv" />
      </section>
    </PageShell>
  )
}
