import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export type CurrentUserAccess = {
  username: string
  roles: string[]
  role: string
  access_level: number
  permissions: string[]
}

export const ADMIN_UTILITY_PERMISSIONS = {
  controlsView: "app.controls:view",
  controlsEdit: "app.controls:edit",
  maintenanceRun: "app.maintenance:run",
  auditView: "audit_log:view",
  ingestManage: "internal.ingest:manage",
  schemasView: "schema:list",
  uiRouteAuditView: "ui.route_audit:view",
  broadcastCreate: "notification.broadcast:create",
} as const

export const ADMIN_ENTRY_PERMISSIONS = [
  "user:list",
  "user:view",
  "role:list",
  "role:view",
  "permission.policy:list",
  "permission.policy:view",
  "assay.panel:list",
  "assay.panel:view",
  "assay.config:list",
  "assay.config:view",
  "gene_list.insilico:list",
  "gene_list.insilico:view",
  "sample:list:global",
  "sample:view:global",
  ...Object.values(ADMIN_UTILITY_PERMISSIONS),
] as const

export function isSuperuser(user: CurrentUserAccess | null | undefined) {
  return Boolean(user?.roles?.includes("superuser"))
}

export function hasPermission(
  user: CurrentUserAccess | null | undefined,
  permission: string,
) {
  return isSuperuser(user) || Boolean(user?.permissions?.includes(permission))
}

export function hasAnyPermission(
  user: CurrentUserAccess | null | undefined,
  permissions: readonly string[],
) {
  return isSuperuser(user) || permissions.some((permission) => hasPermission(user, permission))
}

export function useCurrentUserAccess() {
  return useQuery<CurrentUserAccess>({
    queryKey: ["whoami"],
    queryFn: () => api.get<CurrentUserAccess>("/auth/whoami").then((response) => response.data),
    staleTime: 60_000,
  })
}
