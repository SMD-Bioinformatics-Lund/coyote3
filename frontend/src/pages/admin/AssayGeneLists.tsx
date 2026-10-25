import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { withDocumentEditor } from "@/hooks/useDocumentEditor"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError } from "@/lib/notifications"

type GeneList = {
  isgl_id: string; displayname?: string; name: string; asp_ids: string[]; asp_groups: string[]
  is_active: boolean; version: number; system_installed?: boolean; system_managed?: boolean
}
type Props = {
  aspId: string; aspGroup: string; readonly: boolean; pending?: boolean
  selected?: string[]; onChange?: (ids: string[]) => void
}

/** Show the shared registry; setup selections remain staged until activation. */
export function AssayGeneLists({ aspId, aspGroup, readonly, pending, selected, onChange }: Props) {
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
      await Promise.all([["assay-gene-lists"], ["admin-resource"], ["admin-resource-context"], ["assay-setup-context"]]
        .map((queryKey) => client.invalidateQueries({ queryKey })))
    },
    onError: (error) => {
      notifyActionError("Update gene-list association", error)
      void client.invalidateQueries({ queryKey: ["assay-gene-lists"] })
    },
  })
  return <section aria-label="Existing gene lists" className="glass-card space-y-3 p-3">
    <h3 className="type-card-title">Existing gene lists</h3>
    <p className="type-body-sm text-muted-foreground">Search all registered lists, including unassigned lists.
      {onChange ? " Selections are saved in this draft and applied on activation." : " Links update the gene list’s associated assays."}
      {" "}Association makes a list available; select it in the assay configuration to use it for analysis.</p>
    {!canList ? <p role="status">Gene-list list permission is required to browse existing lists.</p> : <>
      <input aria-label="Search existing gene lists" className="paper-inset w-full rounded-md p-2" value={search}
        onChange={(event) => { setSearch(event.target.value); setPage(1) }} />
      {registry.isLoading && <p role="status">Loading gene lists…</p>}
      {registry.error && <p role="alert">Unable to load gene lists.</p>}
      <ul className="divide-y divide-border">{registry.data?.genelists.map((row) => {
        const linked = onChange ? Boolean(selected?.includes(row.isgl_id)) : row.asp_ids.includes(aspId)
        const protectedList = row.system_installed || row.system_managed
        return <li key={row.isgl_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
          <span><span className="block font-semibold">{row.displayname || row.name}</span><span className="type-meta text-muted-foreground">{row.isgl_id}</span></span>
          <Button size="sm" variant="outline" disabled={!canEdit || pending || mutation.isPending || !row.is_active || protectedList}
            onClick={() => onChange ? onChange(linked ? (selected || []).filter((id) => id !== row.isgl_id) : [...(selected || []), row.isgl_id]) : mutation.mutate(row)}>
            {protectedList ? "System managed" : !row.is_active ? "Inactive" : linked ? "Unlink" : "Link"}
          </Button>
        </li>
      })}</ul>
      {selected && selected.length > 0 && <p className="type-body-sm">Selected: {selected.join(", ")}</p>}
      <div className="flex items-center gap-2"><Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous lists</Button>
        <span className="type-meta">Page {page}</span><Button variant="ghost" size="sm" disabled={!registry.data?.pagination.has_next} onClick={() => setPage(page + 1)}>Next lists</Button></div>
      {hasPermission(access.data, "gene_list.insilico:list") && <Link className="type-body-sm text-primary underline" to="/admin/genelists">Manage gene lists</Link>}
    </>}
  </section>
}
