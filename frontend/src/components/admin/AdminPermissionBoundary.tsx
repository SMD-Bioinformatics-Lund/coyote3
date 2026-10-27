import type { ReactNode } from "react"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"

export function AdminPermissionBoundary({
  permission,
  children,
  area = "Admin",
}: {
  permission: string
  children: ReactNode
  area?: "Admin" | "Clinical"
}) {
  const accessQuery = useCurrentUserAccess()

  if (accessQuery.isLoading) {
    return <AppLoader label={area === "Admin" ? "Loading administration" : "Loading access"} />
  }

  if (!hasPermission(accessQuery.data, permission)) {
    return (
      <PageShell
        eyebrow={area}
        title="Access not assigned"
        description={`Your roles do not grant access to this ${area === "Admin" ? "administrative" : "clinical"} workflow.`}
      >
        <section className="surface-panel p-4 text-sm text-muted-foreground">
          Required permission: <code className="font-semibold text-foreground">{permission}</code>
        </section>
      </PageShell>
    )
  }

  return children
}
