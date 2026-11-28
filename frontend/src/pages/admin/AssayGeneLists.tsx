// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { SearchInput } from "@/components/ui/search-input"
import { api } from "@/lib/api"
import { withDocumentEditor } from "@/hooks/useDocumentEditor"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError } from "@/lib/notifications"
import { assayRevisionQueryKeys } from "./resource-specs"

type GeneList = {
  isgl_id: string; displayname?: string; name: string; asp_ids: string[]; asp_groups: string[]
  is_active: boolean; version: number; system_installed?: boolean; system_managed?: boolean
}
type Props = {
  aspId: string; aspGroup: string; readonly: boolean;
}

/** Manage explicit gene-list links for an installed assay. */
export function AssayGeneLists({ aspId, aspGroup, readonly }: Props) {
  const access = useCurrentUserAccess()
  const client = useQueryClient()
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const canList = hasPermission(access.data, "gene_list.insilico:list")
  const canEdit = !readonly && hasPermission(access.data, "gene_list.insilico:edit")
  const registry = useQuery({
    queryKey: ["assay-gene-lists", search, page], enabled: canList,
    queryFn: () => api.get<{ genelists: GeneList[]; pagination: { has_next: boolean } }>(
      `/resources/genelists?q=${encodeURIComponent(search)}&page=${page}&per_page=30`,
    ).then((response) => response.data),
  })
  const mutation = useMutation({
    mutationFn: (row: GeneList) => withDocumentEditor("genelists", row.isgl_id, (options) => api.put(`/resources/genelists/${encodeURIComponent(row.isgl_id)}`, {
      expected_version: row.version,
      config: {
        asp_ids: row.asp_ids.includes(aspId) ? row.asp_ids.filter((id) => id !== aspId) : [...row.asp_ids, aspId],
        asp_groups: [...new Set([...row.asp_groups, aspGroup])],
      },
    }, options)),
    onSuccess: async () => {
      await Promise.all([["admin-resource", "genelists"], ...assayRevisionQueryKeys]
        .map((queryKey) => client.invalidateQueries({ queryKey })))
    },
    onError: (error) => {
      notifyActionError("Update gene-list association", error)
      void client.invalidateQueries({ queryKey: ["assay-gene-lists"] })
    },
  })
  return <Surface as="section" variant="card" aria-label="Existing gene lists" className="space-y-3 p-3">
    <h3 className="type-card-title">Existing gene lists</h3>
    <p className="type-body-sm text-muted-foreground">Manage explicit assay links. Lists shared with this assay’s group are also available in its configurations.</p>
    {!canList ? <p role="status">Gene-list list permission is required to browse existing lists.</p> : <>
      <SearchInput aria-label="Search existing gene lists" value={search}
        onChange={(event) => { setSearch(event.target.value); setPage(1) }} />
      {registry.isLoading && <p role="status">Loading gene lists…</p>}
      {registry.error && <p role="alert">Unable to load gene lists.</p>}
      <ul className="divide-y divide-border">{registry.data?.genelists.map((row) => {
        const linked = row.asp_ids.includes(aspId)
        const protectedList = row.system_installed || row.system_managed
        return <li key={row.isgl_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
          <span title={row.displayname}><span className="block font-semibold">{row.name || row.displayname || row.isgl_id}</span><span className="type-meta text-muted-foreground">{row.isgl_id}{row.asp_groups.includes(aspGroup) ? " · Available through group" : ""}</span></span>
          <Button size="sm" variant="outline" disabled={!canEdit || mutation.isPending || !row.is_active || protectedList}
            onClick={() => mutation.mutate(row)}>
            {protectedList ? "System managed" : !row.is_active ? "Inactive" : linked ? "Remove assay link" : row.asp_groups.includes(aspGroup) ? "Link assay" : "Link assay and group"}
          </Button>
        </li>
      })}</ul>
      <div className="flex items-center gap-2"><Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous lists</Button>
        <span className="type-meta">Page {page}</span><Button variant="ghost" size="sm" disabled={!registry.data?.pagination.has_next} onClick={() => setPage(page + 1)}>Next lists</Button></div>
      {hasPermission(access.data, "gene_list.insilico:list") && <Link className="type-body-sm text-primary underline" to="/admin/genelists">Manage gene lists</Link>}
    </>}
  </Surface>
}
