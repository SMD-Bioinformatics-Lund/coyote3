import { sanitizeRichText } from "@/lib/safe-html"
import { type ReactNode } from "react"
import { asArray, FIRST_CLASS_CATALOG_FIELDS, formatScalar } from "./catalog-values"

export function HtmlText({ html, className }: { html: unknown; className?: string }) {
  const text = String(html ?? "").trim()
  if (!text) return null
  return <div className={className} dangerouslySetInnerHTML={{ __html: sanitizeRichText(text) }} />
}

export function CatalogField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <span className="mb-1.5 block type-label font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}

export function AdditionalCatalogDetails({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value || {})
    .filter(([key, item]) => !FIRST_CLASS_CATALOG_FIELDS.has(key) && item !== null && item !== undefined && item !== "")
    .filter(([, item]) => {
      if (Array.isArray(item)) return item.length > 0
      if (typeof item === "object") return Object.keys(item as Record<string, unknown>).length > 0
      return true
    })

  if (!entries.length) return null

  return (
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {entries.map(([key, item]) => (
        <CatalogField key={key} label={key.replaceAll("_", " ")}>
          {Array.isArray(item) ? (
            <BadgeList values={item} empty="-" />
          ) : typeof item === "object" ? (
            <div className="space-y-1 text-xs text-muted-foreground">
              {Object.entries(item as Record<string, unknown>).map(([innerKey, innerValue]) => (
                <div key={innerKey} className="flex gap-2">
                  <span className="font-bold uppercase text-foreground/70">{innerKey.replaceAll("_", " ")}</span>
                  <span>{formatScalar(innerValue)}</span>
                </div>
              ))}
            </div>
          ) : (
            <HtmlText html={item} className="text-sm leading-relaxed text-foreground" />
          )}
        </CatalogField>
      ))}
    </div>
  )
}

export function CatalogBadge({ label, value }: { label?: string; value: unknown }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-primary/20 bg-primary/8 px-2 py-0.5 text-xs font-semibold text-primary">
      {label && <span className="text-primary/70">{label}</span>}
      <span className="truncate">{formatScalar(value)}</span>
    </span>
  )
}

export function BadgeList({
  values,
  empty = "-",
  tone = "default",
  compact = false,
}: {
  values: unknown
  empty?: string
  tone?: "default" | "primary" | "secondary" | "success"
  compact?: boolean
}) {
  const list = asArray(values)
  if (!list.length) {
    return empty ? <span className="text-sm text-muted-foreground">{empty}</span> : null
  }
  const toneClass = {
    default: "border-border bg-background text-foreground",
    primary: "border-primary/25 bg-primary/8 text-primary",
    secondary: "border-rna/25 bg-rna/10 text-rna",
    success: "border-pass/25 bg-pass/10 text-pass",
  }[tone]
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((item) => (
        <span
          key={item}
          className={`${toneClass} rounded-full border px-2 ${compact ? "py-0 type-label" : "py-0.5 text-xs"} font-semibold`}
        >
          {item}
        </span>
      ))}
    </div>
  )
}
