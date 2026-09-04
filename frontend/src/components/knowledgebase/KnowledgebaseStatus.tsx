import { CheckCircle2, Cloud, Database, Layers3 } from "lucide-react"

import { TimeDisplay } from "@/components/ui/time-display"
import { databaseLogo } from "@/lib/database-logos"
import { shortCount } from "@/lib/detail-formatters"
import { appPath } from "@/lib/runtime-paths"

export type KnowledgebaseRelease = {
  source: string
  release: string
  status: string
  published_at?: string | null
  records: number
  collections?: Array<{ name: string; records: number }>
}

export type KnowledgebaseStatusPayload = {
  releases?: KnowledgebaseRelease[]
  summary?: {
    installed_products?: number
    configured_services?: number
    available_products?: number
    total_records?: number
  }
}

const familyLabels: Record<string, string> = {
  brca_exchange: "BRCA Exchange",
  civic: "CIViC",
  clinpgx: "ClinPGx",
  hpa: "Human Protein Atlas",
  iarc_tp53: "IARC TP53",
  nci_tp53: "NCI TP53",
  oncokb: "OncoKB",
}

function sourceDetails(source: string) {
  if (source.startsWith("cosmic_")) {
    return { family: "COSMIC", product: source.slice(7).replaceAll("_", " ") }
  }
  const familyKey = Object.keys(familyLabels).find((key) => source.startsWith(key))
  const suffix = familyKey ? source.slice(familyKey.length).replace(/^_/, "") : ""
  return {
    family: familyKey ? familyLabels[familyKey] : source.replaceAll("_", " "),
    product: suffix ? suffix.replaceAll("_", " ") : "reference",
  }
}

export function KnowledgebaseStatus({
  payload,
  compact = false,
}: {
  payload?: KnowledgebaseStatusPayload
  compact?: boolean
}) {
  const releases = payload?.releases || []
  const totalRecords = payload?.summary?.total_records
    ?? releases.reduce((total, release) => total + Number(release.records || 0), 0)

  if (!releases.length) {
    return (
      <div className="bg-card px-4 py-5 text-center type-body-sm text-muted-foreground">
        No installed knowledgebase releases are recorded.
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-border bg-success/5 px-4 py-3">
        <div className="flex items-baseline gap-1.5">
          <span className="type-card-title text-primary">
            {shortCount(payload?.summary?.available_products ?? releases.length)}
          </span>
          <span className="type-meta text-muted-foreground">available products</span>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="type-card-title text-foreground">{shortCount(totalRecords)}</span>
          <span className="type-meta text-muted-foreground">indexed records</span>
        </div>
      </div>

      <div className="grid gap-2 bg-card p-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {releases.map((release) => {
          const details = sourceDetails(release.source)
          const logo = databaseLogo(release.source)
          return (
            <article key={release.source} className="static-info-card min-w-0 p-3" data-static-tone="success">
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-start gap-2">
                  {logo ? (
                    <span className="flex h-7 w-16 shrink-0 items-center justify-center">
                      <img src={appPath(logo.src)} alt={logo.alt} className="max-h-6 max-w-full object-contain" />
                    </span>
                  ) : (
                    <span className="static-icon flex size-7 shrink-0 items-center justify-center rounded-md">
                      <Database className="size-3.5" aria-hidden="true" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="type-body-sm truncate text-foreground">{details.family}</p>
                    <p className="type-label mt-0.5 capitalize text-muted-foreground">{details.product}</p>
                  </div>
                </div>
                {release.status === "configured" ? (
                  <Cloud className="size-4 shrink-0 text-info" aria-label="Configured remote service" />
                ) : (
                  <CheckCircle2 className="size-4 shrink-0 text-pass" aria-label="Installed" />
                )}
              </div>
              <div className="mt-2 flex items-end justify-between gap-3">
                <div>
                  <p className="type-label uppercase text-muted-foreground">Release</p>
                  <p className="type-meta text-foreground">{release.release}</p>
                </div>
                <div className="text-right">
                  <p className="type-label uppercase text-muted-foreground">Records</p>
                  <p className="type-meta text-foreground">{shortCount(release.records)}</p>
                </div>
              </div>
              {!compact && release.collections?.length ? (
                <div className="mt-2 flex items-center gap-1.5 border-t border-border pt-2 type-label text-muted-foreground">
                  <Layers3 className="size-3.5" />
                  {release.collections.length} collection{release.collections.length === 1 ? "" : "s"}
                </div>
              ) : null}
              {!compact && release.published_at ? (
                <div className="mt-1 flex items-center gap-1.5 type-label text-muted-foreground">
                  <Database className="size-3.5" />
                  <TimeDisplay value={release.published_at} />
                </div>
              ) : null}
            </article>
          )
        })}
      </div>
    </div>
  )
}
