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
import { adminFields, adminSearchValue } from "@/pages/admin/resource-list"
import { csvCellText } from "@/lib/csv-export"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"

const NO_INVALIDATIONS: string[][] = []
const NO_COLUMNS: string[] = []
export function useAdminList({ spec, filters, preferredColumns = NO_COLUMNS, serverFilters = false, sampleNotifications = false, invalidateKeys = NO_INVALIDATIONS }: { spec: AdminResourceSpec; filters: ResourceListFilter[]; preferredColumns?: string[]; serverFilters?: boolean; sampleNotifications?: boolean; invalidateKeys?: string[][] }) {
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
  const [versionHistory, setVersionHistory] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<{ action: "toggle" | "delete" | "invite"; id: string; name: string } | null>(null)

  useEffect(() => {
    setResourceFilters({})
    setQ("")
    setPendingAction(null)
    setVersionHistory(null)
  }, [filters])

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "admin-resource",
      spec.key,
      serverFilters ? q : "",
      serverFilters ? resourceFilters : null,
    ],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams()
      if (serverFilters && q) params.set(spec.searchParam ?? "q", q)
      if (serverFilters) {
        for (const { field } of filters) {
          if (resourceFilters[field]) params.set(field, resourceFilters[field])
        }
      }
      params.set("per_page", String(Math.max(...TABLE_PAGE_SIZE_OPTIONS)))
      const response = await api.get(`${spec.endpoint}?${params.toString()}`, { signal })
      if (serverFilters) return response.data
      const records = [...(response.data?.[spec.listKey] || [])]
      const total = response.data?.pagination?.total ?? records.length
      for (let page = 2; records.length < total; page++) {
        params.set("page", String(page))
        const next = await api.get(`${spec.endpoint}?${params.toString()}`, { signal })
        const batch = next.data?.[spec.listKey] || []
        if (!batch.length) throw new Error("Resource list changed; reload before searching")
        records.push(...batch)
      }
      return { ...response.data, [spec.listKey]: records }
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
    // Retain the public metadata previously searched by the resource APIs as well.
    const fields = [...new Set([...adminFields(preferredColumns, rows),
      "description", "aliases", "firstname", "lastname", "job_title", "color",
    ])]
    const query = q.trim().toLocaleLowerCase()
    return rows.filter((row) => rowMatchesResourceFilters(row, listFilterDefinitions, resourceFilters)
      && (serverFilters || !query || fields.some(field => csvCellText(adminSearchValue(field, row)).toLocaleLowerCase().includes(query))))
  }, [listFilterDefinitions, resourceFilters, rows, q, serverFilters, preferredColumns])

  return { accessQuery, canList, canView, canCreate, canEdit, canDelete, data, isLoading, error, rows, visibleRows, q, setQ, resourceFilters, setResourceFilters, listFilterDefinitions, listFilterOptions, pendingAction, setPendingAction, mutate, versionHistory, setVersionHistory }
}
export type AdminListState = ReturnType<typeof useAdminList>
