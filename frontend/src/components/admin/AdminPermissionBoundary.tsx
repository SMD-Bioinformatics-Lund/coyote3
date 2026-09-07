import type { ReactNode } from "react"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"

export function AdminPermissionBoundary({
  permission,
  children,
}: {
  permission: string
  children: ReactNode
}) {
  const accessQuery = useCurrentUserAccess()

  if (accessQuery.isLoading) {
    return (
      <PageShell eyebrow="Admin" title="Checking access">
        <AppLoader label="Checking administration access" />
      </PageShell>
    )
  }

  if (!hasPermission(accessQuery.data, permission)) {
    return (
      <PageShell
        eyebrow="Admin"
        title="Access not assigned"
        description="Your roles do not grant access to this administrative workflow."
      >
        <section className="surface-panel p-4 text-sm text-muted-foreground">
          Required permission: <code className="font-semibold text-foreground">{permission}</code>
        </section>
      </PageShell>
    )
  }

  return children
}
