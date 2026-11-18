// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Notice } from "@/components/ui/notice"
import { Badge } from "@/components/ui/badge"
import { AppLoader } from "@/components/layout/AppLoader"
import { sanitizeRichText } from "@/lib/safe-html"
import { asList, display } from "./resource-values"

export function Loading() {
  return <AppLoader label="Loading reference data" />
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <Notice tone="danger">
      {error instanceof Error ? error.message : "Unable to load data"}
    </Notice>
  )
}

export function InfoTile({ label, value, mono = false }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <dt className="type-label font-semibold uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={`mt-1 break-words text-sm font-semibold ${mono ? "" : ""}`}>{display(value)}</dd>
    </div>
  )
}

export function ChipList({ values, empty = "None recorded" }: { values: unknown; empty?: string }) {
  const items = asList(values)
  if (!items.length) return <span className="text-sm text-muted-foreground">{empty}</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge variant="outline" key={item} className="border-border bg-muted">
          {item}
        </Badge>
      ))}
    </div>
  )
}

export function SectionTitle({ icon: Icon, children }: { icon: any; children: string }) {
  return (
    <h2 className="type-card-title mb-3 flex items-center gap-2 text-foreground">
      <Icon className="h-4 w-4 text-primary" />
      {children}
    </h2>
  )
}

export function HtmlText({ value, className = "" }: { value: unknown; className?: string }) {
  const html = String(value || "").trim()
  if (!html) return null
  return (
    <div
      className={`prose prose-sm max-w-none text-sm leading-relaxed text-muted-foreground dark:prose-invert prose-a:text-primary ${className}`}
      dangerouslySetInnerHTML={{ __html: sanitizeRichText(html) }}
    />
  )
}

export function BadgeList({
  values,
  empty = "Not specified",
  tone = "default",
}: {
  values: unknown
  empty?: string
  tone?: "default" | "sample" | "analysis" | "material"
}) {
  const items = asList(values)
  const toneClass = {
    default: "border-border bg-muted text-foreground",
    sample: "border-primary/25 bg-primary/10 text-primary",
    analysis: "border-tier2/30 bg-tier2/10 text-tier2",
    material: "border-pass/30 bg-pass/10 text-pass",
  }[tone]
  if (!items.length) return <span className="text-sm text-muted-foreground">{empty}</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge variant="outline" key={item} className={`${toneClass}`}>
          {item}
        </Badge>
      ))}
    </div>
  )
}
