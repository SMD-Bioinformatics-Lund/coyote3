import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { AdminResourceSpec } from "@/pages/admin/resource-specs"

/** Inspect immutable resource revisions only after the operator requests history. */
export function ResourceVersionHistory({ spec, identifier, onClose }: {
  spec: AdminResourceSpec
  identifier: string
  onClose: () => void
}) {
  const [search, setSearch] = useState(identifier)
  const [selected, setSelected] = useState(identifier)
  const versions = useQuery({
    queryKey: ["admin-resource-versions", spec.key, selected],
    enabled: Boolean(selected),
    queryFn: () => api.get<Record<string, unknown>[]>(
      `${spec.endpoint}/${encodeURIComponent(selected)}/versions`,
    ).then(response => response.data),
  })
  return <section className="surface-panel my-4 space-y-3 p-4" aria-label={`${spec.title} version history`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="type-section-title">Version history</h2>
      <Button variant="outline" size="sm" onClick={onClose}>Close history</Button>
    </div>
    <p className="type-body-sm text-muted-foreground">Current and retired revisions are read-only. Existing samples retain their applied versions.</p>
    <form className="flex flex-wrap gap-2" onSubmit={event => {
      event.preventDefault()
      const identifier = search.trim()
      if (!identifier || versions.isFetching) return
      if (identifier === selected) void versions.refetch()
      else setSelected(identifier)
    }}>
      <Input autoFocus aria-label="Resource identifier for history" placeholder={spec.idKeys[0]} value={search} onChange={event => setSearch(event.target.value)} />
      <Button type="submit" variant="outline" disabled={!search.trim() || versions.isFetching}>Load versions</Button>
    </form>
    {versions.isFetching ? <p role="status">Loading versions…</p> : versions.isError ? <p role="alert">Unable to load version history. <Button variant="link" onClick={() => void versions.refetch()}>Retry</Button></p>
      : selected && !versions.data?.length ? <p role="status">No retained versions for this identifier.</p>
      : versions.data?.map((version, index) => <details key={String(version._id ?? index)} className="paper-inset rounded-lg border border-border p-3">
        <summary className="cursor-pointer type-body-sm">Version {String(version.version ?? "—")} · {version.is_active ? "Current" : "Retired"}{version.updated_by ? ` · ${String(version.updated_by)}` : ""}</summary>
        <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all type-supporting">{JSON.stringify(version, null, 2)}</pre>
      </details>)}
  </section>
}
