import type { ComponentType } from "react"
import { Link } from "react-router-dom"
import {
  Database,
  Dna,
  FileUp,
  KeyRound,
  ListTree,
  Megaphone,
  Settings2,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  UsersRound,
} from "lucide-react"

import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
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

export function AdminHubPage() {
  const accessQuery = useCurrentUserAccess()
  const modulesQuery = useApplicationModules()
  const user = accessQuery.data
  const visibleResources = Object.values(specs).filter((spec) => hasPermission(user, spec.permissions.list))
  const visibleUtilities = utilityModules.filter((module) =>
    hasPermission(user, module.permission)
    && (module.href !== "/admin/ingest" || moduleIsEnabled(modulesQuery.data, "ingest_workspace"))
  )

  return (
    <PageShell
      eyebrow="Admin"
      title="Admin Settings"
      description="Govern identity, assays, configurations, ingestion, audit events, and platform contracts."
    >
      {accessQuery.isLoading ? (
        <AppLoader label="Loading administration access" />
      ) : visibleResources.length === 0 && visibleUtilities.length === 0 ? (
        <section className="surface-panel p-5">
          <h2 className="text-base font-semibold">Administration access is not assigned</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Your roles do not include permission to view an administrative resource.
          </p>
        </section>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visibleResources.map((spec) => {
            const Icon = resourceIcons[spec.key] || Settings2
            return (
              <Link key={spec.key} to={`/admin/${spec.key}`} className="glass-card p-4 transition-colors hover:bg-muted/40">
                <div className="mb-2 inline-flex rounded-lg bg-primary/10 p-2 text-primary">
                  <Icon className="h-4 w-4" />
                </div>
                <h2 className="font-semibold">{spec.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{spec.description}</p>
              </Link>
            )
          })}
          {visibleUtilities.map((module) => (
            <Link key={module.href} to={module.href} className="glass-card p-4 transition-colors hover:bg-muted/40">
              <div className="mb-2 inline-flex rounded-lg bg-primary/10 p-2 text-primary">
                <module.icon className="h-4 w-4" />
              </div>
              <h2 className="font-semibold">{module.title}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{module.description}</p>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  )
}
