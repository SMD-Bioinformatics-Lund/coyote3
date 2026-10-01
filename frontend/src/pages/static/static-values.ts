import { appPath } from "@/lib/runtime-paths"


export type ContactPerson = { name?: string; email: string }

export type ContactChannel = {
  label?: string
  role?: string
  description?: string
  email?: string
  phone?: string
  people?: ContactPerson[]
}

export type PublicContactPayload = {
  organization: Record<string, string>
  support: Record<string, string>
  codebase?: Record<string, string>
  contacts: ContactChannel[]
  links: Array<Record<string, string>>
  hours: Array<Record<string, string>>
}

export type PublicAboutPayload = PublicContactPayload & {
  application: Record<string, any>
  references: Record<string, any>
  software: Record<string, any>
  databases: Record<string, any>
  software_links?: LinkLike[]
  knowledgebase_status?: import("@/components/knowledgebase/KnowledgebaseStatus").KnowledgebaseStatusPayload
}

export type LinkLike = Record<string, string>

export type StaticTone = "primary" | "info" | "success" | "warning"

export const STATIC_TONES: StaticTone[] = ["primary", "info", "success", "warning"]

export function humanLabel(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

export function buildAboutLinks(configuredLinks: LinkLike[], codebase: Record<string, string>) {
  const defaults: LinkLike[] = [
    {
      label: "User documentation",
      url: "/docs-site/",
      description: "Clinical user guide, deployment notes, and operating procedures.",
      icon: "docs",
    },
    codebase.license_url ? {
      label: "License",
      url: codebase.license_url,
      description: "Project license and deployment notices.",
    } : null,
    codebase.repository_url ? {
      label: "GitHub repository",
      url: codebase.repository_url,
      description: "Source repository, code review, and release history.",
      icon: "github",
    } : null,
    codebase.bug_report_url ? {
      label: "Report a Bug",
      url: codebase.bug_report_url,
      description: "Report an application defect or reproducible malfunction.",
      icon: "bug",
    } : null,
    codebase.feature_request_url ? {
      label: "Request a Feature",
      url: codebase.feature_request_url,
      description: "Suggest a product improvement or workflow enhancement.",
      icon: "feature",
    } : null,
    codebase.support_request_url ? {
      label: "Support",
      url: codebase.support_request_url,
      description: "Ask for help with setup, usage, access, or operational behavior.",
      icon: "issue",
    } : null,
  ].filter(Boolean) as LinkLike[]
  const byUrl = new Map<string, LinkLike>()
  for (const link of [...defaults, ...configuredLinks]) {
    if (!link.url) continue
    byUrl.set(link.url, link)
  }
  return Array.from(byUrl.values())
}

export function publicHref(url?: string) {
  if (!url) return "#"
  if (/^https?:\/\//i.test(url) || url.startsWith("mailto:") || url.startsWith("tel:")) return url
  return appPath(url)
}

export function isExternalHref(url?: string) {
  return Boolean(url && /^https?:\/\//i.test(url))
}
