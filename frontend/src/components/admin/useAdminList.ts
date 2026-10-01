import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { TABLE_PAGE_SIZE_OPTIONS } from "@/lib/user-settings"
import type { ResourceListFilter } from "@/pages/admin/resource-list"
import {
  mutationDisplayName,
  mutationResourceId,
  resourceFilterValues,
  rowMatchesResourceFilters
} from "@/pages/admin/resource-list"
import {
  actionLabels,
  type AdminResourceSpec
} from "@/pages/admin/resource-specs"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"

const NO_INVALIDATIONS: string[][] = []
export function useAdminList({ spec, filters, serverFilters = false, sampleNotifications = false, invalidateKeys = NO_INVALIDATIONS }: { spec: AdminResourceSpec; filters: ResourceListFilter[]; serverFilters?: boolean; sampleNotifications?: boolean; invalidateKeys?: string[][] }) {
  const accessQuery = useCurrentUserAccess()
  const user = accessQuery.data
  const canList = hasPermission(user, spec.permissions.list)
  const canView = hasPermission(user, spec.permissions.view)
  const canCreate = hasPermission(user, spec.permissions.create)
  const canEdit = hasPermission(user, spec.permissions.edit)
  const canDelete = hasPermission(user, spec.permissions.delete)
  const queryClient = useQueryClient()
  const [q, setQ] = useState("")
  const [resourceFilters, setResourceFilters] = useState<Record<string, string>>({})
  const [pendingAction, setPendingAction] = useState<{ action: "toggle" | "delete" | "invite"; id: string; name: string } | null>(null)

  useEffect(() => {
    setResourceFilters({})
    setQ("")
    setPendingAction(null)
  }, [filters])

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "admin-resource",
      spec.key,
      q,
      serverFilters ? resourceFilters : null,
    ],
    queryFn: () => {
      const params = new URLSearchParams()
      if (q) params.set(spec.searchParam ?? "q", q)
      if (serverFilters) {
        for (const { field } of filters) {
          if (resourceFilters[field]) params.set(field, resourceFilters[field])
        }
      }
      params.set("per_page", String(Math.max(...TABLE_PAGE_SIZE_OPTIONS)))
      return api.get(`${spec.endpoint}?${params.toString()}`).then((res) => res.data)
    },
    enabled: canList,
  })

  const mutate = useMutation({
    mutationFn: ({ action, id }: { action: "toggle" | "delete" | "invite"; id: string; name: string }) => {
      if (action === "invite") return api.post(`${spec.endpoint}/${id}/invite`, {})
      if (action === "toggle") return api.patch(`${spec.endpoint}/${id}/status`, {})
      return api.delete(`${spec.endpoint}/${id}`)
    },
    onSuccess: (result, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      for (const queryKey of invalidateKeys) queryClient.invalidateQueries({ queryKey })
      setPendingAction(null)
      const displayName = mutationDisplayName(result, variables.name)
      const resourceId = mutationResourceId(result, variables.id)
      notifySuccess(
        `${spec.title} ${actionLabels[variables.action]}`,
        `${displayName} was ${actionLabels[variables.action]}.`,
        `Admin ${spec.key}`,
        {
          type: spec.key,
          id: resourceId,
          name: displayName,
          sampleName: sampleNotifications ? displayName : undefined,
        }
      )
    },
    onError: (error, variables) => {
      notifyActionError(
        `Unable to ${variables.action} ${spec.title.toLowerCase()}`,
        error,
        `Admin ${spec.key}`,
        {
          type: spec.key,
          id: variables.id,
          name: variables.name,
          sampleName: sampleNotifications ? variables.name : undefined,
        }
      )
    },
  })

  const rows = useMemo(() => (data?.[spec.listKey] || []) as any[], [data, spec.listKey])
  const listFilterDefinitions = filters
  const listFilterOptions = useMemo(() => {
    return Object.fromEntries(listFilterDefinitions.map((definition, index) => {
      const serverOptions = data?.filter_options?.[definition.field]
      if (serverFilters && Array.isArray(serverOptions)) {
        return [definition.field, serverOptions]
      }
      const parentDefinitions = listFilterDefinitions.slice(0, index)
      const candidateRows = rows.filter((row) =>
        rowMatchesResourceFilters(row, parentDefinitions, resourceFilters)
      )
      const options = Array.from(
        new Set(candidateRows.flatMap((row) => resourceFilterValues(row, definition.field)))
      ).sort((left, right) => left.localeCompare(right))
      return [definition.field, options]
    })) as Record<string, string[]>
  }, [data?.filter_options, listFilterDefinitions, resourceFilters, rows, serverFilters])
  const visibleRows = useMemo(() => {
    return rows.filter((row) => rowMatchesResourceFilters(row, listFilterDefinitions, resourceFilters))
  }, [listFilterDefinitions, resourceFilters, rows])

  return { accessQuery, canList, canView, canCreate, canEdit, canDelete, data, isLoading, error, rows, visibleRows, q, setQ, resourceFilters, setResourceFilters, listFilterDefinitions, listFilterOptions, pendingAction, setPendingAction, mutate }
}
export type AdminListState = ReturnType<typeof useAdminList>
