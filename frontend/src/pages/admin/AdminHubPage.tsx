import { useState, type ComponentType } from "react"
import { Link } from "react-router-dom"
import {
  Beaker,
  ChevronRight,
  BookOpenCheck,
  Database,
  Dna,
  FilePenLine,
  FileUp,
  KeyRound,
  ListTree,
  Megaphone,
  Settings2,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  UsersRound,
  Search,
  X,
  RefreshCw,
} from "lucide-react"

import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  ADMIN_UTILITY_PERMISSIONS,
  hasPermission,
  useCurrentUserAccess,
} from "@/lib/access-control"
import { moduleIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { specs } from "@/pages/admin/resource-specs"

const resourceIcons: Record<string, ComponentType<{ className?: string }>> = {
  users: UsersRound,
  roles: Shield,
  permissions: KeyRound,
  asp: Dna,
  aspc: SlidersHorizontal,
  genelists: ListTree,
  samples: Database,
}

const utilityModules = [
  {
    title: "Query Rule Testing",
    description: "Compare query-rule versions against authorized samples without changing findings.",
    href: "/admin/query-rules/testing",
    icon: Beaker,
    permission: "query_rules:test",
  },
  {
    title: "Query rules",
    description: "Review inherited finding-selection policies and publish scoped exceptions.",
    href: "/admin/query-rules",
    icon: SlidersHorizontal,
    permission: "query_rules:view",
  },
  {
    title: "Assay groups",
    description: "View system groups and register center-owned assay groups.",
    href: "/admin/assay-groups",
    icon: ListTree,
    permission: "assay.panel:view",
  },
  {
    title: "Assay setup",
    description: "Prepare assay scopes, gene lists, reporting rules and configurations for review.",
    href: "/admin/assay-setups",
    icon: Dna,
    permission: "assay.panel:view",
  },
  {
    title: "Subpanel definitions",
    description: "Create shared subpanels and select their assays.",
    href: "/admin/subpanels",
    icon: ListTree,
    permission: "assay.panel:view",
  },
  {
    title: "Assay subpanel associations",
    description: "Enable or disable subpanels for each assay.",
    href: "/admin/assay-subpanels",
    icon: SlidersHorizontal,
    permission: "assay.panel:view",
  },
  {
    title: "Assay Catalog",
    description: "Manage public assay narrative, modality structure, and portable JSON imports and exports.",
    href: "/admin/assay-catalog",
    icon: FilePenLine,
    permission: "catalog:view",
  },
  {
    title: "Reporting Rule Sets",
    description: "Author, review, validate, and publish governed clinical report wording.",
    href: "/admin/clinical-rules",
    icon: BookOpenCheck,
    permission: ADMIN_UTILITY_PERMISSIONS.clinicalRulesView,
  },
  {
    title: "Clinical Rule Testing",
    description: "Test rule-set versions against authorized samples without persisting reports or sample changes.",
    href: "/admin/clinical-rules/testing",
    icon: Beaker,
    permission: ADMIN_UTILITY_PERMISSIONS.clinicalRulesTest,
  },
  {
    title: "Application Controls",
    description: "Manage runtime module switches, Celery task gates, and retention settings.",
    href: "/admin/controls",
    icon: Settings2,
    permission: ADMIN_UTILITY_PERMISSIONS.controlsView,
  },
  {
    title: "Audit",
    description: "Review administrative and workflow audit events.",
    href: "/admin/audit",
    icon: ShieldCheck,
    permission: ADMIN_UTILITY_PERMISSIONS.auditView,
  },
  {
    title: "Ingest Workspace",
    description: "Queue validated sample-bundle ingestion and inspect worker task state.",
    href: "/admin/ingest",
    icon: FileUp,
    permission: ADMIN_UTILITY_PERMISSIONS.ingestManage,
  },
  {
    title: "UI Route Audit",
    description: "Review frontend routes, API dependencies, and consumed payload fields.",
    href: "/admin/ui-routes",
    icon: ShieldCheck,
    permission: ADMIN_UTILITY_PERMISSIONS.uiRouteAuditView,
  },
  {
    title: "Broadcast Notifications",
    description: "Send application information, warnings, and maintenance notices to all or selected users.",
    href: "/admin/notifications",
    icon: Megaphone,
    permission: ADMIN_UTILITY_PERMISSIONS.broadcastCreate,
  },
] as const

const adminSections = [
  { id: "assays", title: "Assays and subpanels", icon: Dna, paths: ["assay-groups", "assay-setups", "asp", "subpanels", "assay-subpanels", "aspc", "genelists"] },
  { id: "reporting", title: "Clinical rules and catalog", icon: BookOpenCheck, paths: ["query-rules", "query-rules/testing", "clinical-rules", "clinical-rules/testing", "assay-catalog"] },
  { id: "access", title: "Identity and access", icon: UsersRound, paths: ["users", "roles", "permissions"] },
  { id: "operations", title: "Application operations", icon: Settings2, paths: ["samples", "ingest", "controls", "notifications", "audit", "ui-routes"] },
] as const

export function AdminHubPage() {
  const accessQuery = useCurrentUserAccess()
  const modulesQuery = useApplicationModules()
  const [search, setSearch] = useState("")
  const user = accessQuery.data
  const visibleResources = Object.values(specs).filter((spec) => hasPermission(user, spec.permissions.list))
  const authorizedUtilities = utilityModules.filter((module) =>
    hasPermission(user, module.permission)
    && (!["/admin/subpanels", "/admin/assay-subpanels", "/admin/assay-setups"].includes(module.href) || hasPermission(user, "assay.panel:list"))
  )
  const visibleUtilities = authorizedUtilities.filter(module => module.href !== "/admin/ingest" || (!modulesQuery.isLoading && !modulesQuery.isError && moduleIsEnabled(modulesQuery.data, "ingest_workspace")))
  const links = [
    ...visibleResources.map((spec) => ({
      title: spec.title, description: spec.description, href: `/admin/${spec.key}`,
      icon: resourceIcons[spec.key] || Settings2,
    })),
    ...visibleUtilities,
  ]
  const sections = adminSections.map(section => ({
    ...section,
    items: section.paths.flatMap(path => links.filter(link => link.href === `/admin/${path}`)),
  })).filter(section => section.items.length > 0)
  const needle = search.trim().toLowerCase()
  const matching = sections.map(section => ({
    ...section,
    items: section.items.filter(item => `${section.title} ${item.title} ${item.description}`.toLowerCase().includes(needle)),
  })).filter(section => section.items.length > 0)

  return (
    <PageShell
      eyebrow="Admin"
      title="Administration"
      description="Manage assays, reporting, user access and application settings."
    >
      {accessQuery.isLoading ? (
        <AppLoader label="Loading administration access" />
      ) : accessQuery.isError ? (
        <div role="alert" className="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
          <p>Unable to load administration access.</p>
          <Button variant="outline" onClick={() => void accessQuery.refetch()}><RefreshCw className="size-4" />Retry</Button>
        </div>
      ) : visibleResources.length === 0 && authorizedUtilities.length === 0 ? (
        <section className="surface-panel p-5">
          <h2 className="text-base font-semibold">Administration access is not assigned</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Your roles do not include permission to view an administrative resource.
          </p>
        </section>
      ) : (
        <div className="min-w-0">
          <div className="glass-card space-y-3 bg-card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative w-full sm:max-w-md">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                <Input className="pl-9 pr-10" aria-label="Search administration" placeholder="Search administration" value={search} onChange={event => setSearch(event.target.value)} />
                {search && <Button variant="ghost" size="icon" className="absolute right-0 top-0" title="Clear search" aria-label="Clear search" onClick={() => setSearch("")}><X className="size-4" /></Button>}
              </div>
              <span role="status" className="type-meta text-muted-foreground">{matching.reduce((total, section) => total + section.items.length, 0)} destinations</span>
            </div>
          </div>
          {modulesQuery.isError && hasPermission(user, ADMIN_UTILITY_PERMISSIONS.ingestManage) && <div role="alert" className="flex flex-wrap items-center gap-3 type-body-sm"><p>Ingest availability could not be checked.</p><Button variant="outline" onClick={() => void modulesQuery.refetch()}><RefreshCw className="size-4" />Retry module status</Button></div>}
          {!matching.length && <div className="py-6 text-center"><p className="type-body text-muted-foreground">No administrative pages match this search.</p><Button className="mt-3" variant="outline" onClick={() => setSearch("")}><X className="size-4" />Clear search</Button></div>}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {matching.map((section) => {
            const items = section.items
            const tone = { assays: "primary", reporting: "success", access: "info", operations: "warning" }[section.id]
            return <section key={section.id} aria-labelledby={`admin-${section.id}`} data-static-tone={tone} className="admin-category min-w-0 rounded-lg p-4 sm:p-5">
              <div className="mb-4 flex items-center gap-3">
                <span className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${tone === "primary" ? "bg-primary/10 text-primary" : "static-icon"}`}><section.icon className="size-5" aria-hidden="true" /></span>
                <h2 id={`admin-${section.id}`} className="type-card-title">{section.title}</h2>
                <span className="ml-auto type-meta text-muted-foreground">{items.length} tools</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {items.map((item) => <Link key={item.href} to={item.href} className="admin-destination group flex min-w-0 items-start gap-3 p-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className={`flex size-8 shrink-0 items-center justify-center rounded-md ${tone === "primary" ? "bg-primary/10 text-primary" : "static-icon"}`}><item.icon className="size-4" aria-hidden="true" /></span>
                  <div className="min-w-0 flex-1 break-words">
                    <h3 className="type-body font-semibold">{item.title}</h3>
                    <p className="mt-1 type-body-sm text-muted-foreground">{item.description}</p>
                  </div>
                  <ChevronRight className="mt-2 h-4 w-4 shrink-0 text-muted-foreground group-hover:text-primary" aria-hidden="true" />
                </Link>)}
              </div>
            </section>
          })}
          </div>
        </div>
      )}
    </PageShell>
  )
}
