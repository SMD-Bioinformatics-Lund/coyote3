import { useEffect, useRef, useState, type ChangeEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { Check, Download, Edit, Eye, FileUp, Plus, Save, Send, X } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { downloadJson } from "@/lib/json-download"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { CatalogBuilder } from "./CatalogBuilder"
import type { Catalog, Version, Workspace } from "./catalog-types"
import { CatalogPreview } from "./CatalogPreview"

export function PublicAssayCatalogPage() {
  const access = useCurrentUserAccess()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const id = params.get("version") || ""
  const [draft, setDraft] = useState<Catalog | null>(null)
  const [section, setSection] = useState("")
  const [entry, setEntry] = useState("")
  const [editing, setEditing] = useState(false)
  const [reviewer, setReviewer] = useState("")
  const [publisher, setPublisher] = useState("")
  const [reason, setReason] = useState("")
  const [confirmPublish, setConfirmPublish] = useState(false)
  const upload = useRef<HTMLInputElement>(null)
  const allowed = (p: string) => hasPermission(access.data, p)
  const workspace = useQuery({
    queryKey: ["admin-public-assay-catalog"],
    queryFn: () => api.get<Workspace>("/admin/assay-catalog").then((r) => r.data),
    enabled: allowed("catalog:view"),
    refetchOnWindowFocus: false,
  })
  const versionQuery = useQuery({
    queryKey: ["catalog-version", id],
    queryFn: () => api.get<Version>(`/admin/assay-catalog/versions/${id}`).then((r) => r.data),
    enabled: Boolean(id) && allowed("catalog:view"),
    refetchOnWindowFocus: false,
  })
  const version = id ? versionQuery.data : undefined
  const original = id ? version?.catalog : workspace.data?.catalog
  useEffect(() => { setDraft(original ? structuredClone(original) : null) }, [original])
  const dirty = Boolean(draft && original && JSON.stringify(draft) !== JSON.stringify(original))
  const editable = Boolean(version?.status === "draft" && allowed("catalog:draft"))
  useEffect(() => {
    const beforeUnload = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault() }
    window.addEventListener("beforeunload", beforeUnload)
    return () => window.removeEventListener("beforeunload", beforeUnload)
  }, [dirty])
  const [pendingSelection, setPendingSelection] = useState<string | null>(null)
  const select = (oid: string) => {
    if (oid === id || mutation.isPending) return
    if (dirty) { setPendingSelection(oid); return }
    setParams(oid ? { version: oid } : {})
    setEditing(false); setReviewer(""); setPublisher(""); setReason("")
  }
  const mutation = useMutation({
    mutationFn: async ({ action, document }: { action: string; document?: unknown }) => {
      const base = "/admin/assay-catalog"
      if (action === "create") return (await api.post<Version>(`${base}/drafts`)).data
      if (action === "import") return (await api.post<Version>(`${base}/imports`, { document })).data
      if (action === "save") return (await api.patch<Version>(`${base}/drafts/${id}`,
        { revision: version?.revision, catalog: draft })).data
      return (await api.post<Version>(`${base}/drafts/${id}/${action === "reject" ? "review" : action}`,
        { revision: version?.revision, assignee: action === "submit" ? reviewer : publisher,
          approve: action !== "reject", reason })).data
    },
    onSuccess: (saved, request) => {
      qc.setQueryData(["catalog-version", saved._id], saved)
      setDraft(structuredClone(saved.catalog))
      setParams({ version: saved._id })
      setEditing(request.action === "create" || request.action === "import")
      setConfirmPublish(false)
      void qc.invalidateQueries({ queryKey: ["admin-public-assay-catalog"] })
      if (request.action === "publish") {
        void qc.invalidateQueries({ predicate: (query) => query.queryKey.some(
          (key) => typeof key === "string" && (key.includes("catalog") || key.includes("assay-catalog"))) })
      }
      notifySuccess(request.action === "save" ? "Draft saved for preview" : "Catalog workflow updated", "", "Catalog")
    },
    onError: (error) => notifyActionError("Catalog action failed", error, "Catalog"),
  })
  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ""
    if (!file) return
    try { mutation.mutate({ action: "import", document: JSON.parse(await file.text()) }) }
    catch (error) { notifyActionError("Invalid catalog JSON", error, "Catalog") }
  }
  const [historyOpen, setHistoryOpen] = useState(false)
  const history = useQuery({
    queryKey: ["catalog-history", id, version?.revision],
    queryFn: () => api.get<{ items: { revision: number; document: Version }[] }>(
      `/admin/assay-catalog/versions/${id}/revisions`).then((r) => r.data.items),
    enabled: Boolean(id) && historyOpen && allowed("catalog:view"),
  })
  const [snapshot, setSnapshot] = useState<Version | null>(null)
  useEffect(() => { setSnapshot(null) }, [id, version?.revision])
  if (access.isLoading) return <PageShell title="Public Assay Catalog"><AppLoader label="Loading permissions" /></PageShell>
  if (!allowed("catalog:view")) return <PageShell title="Public Assay Catalog"><p>Catalog access is required.</p></PageShell>
  if (workspace.isError || versionQuery.isError) return <PageShell title="Public Assay Catalog"><p role="alert">The catalog could not be loaded.</p><Button onClick={() => { void workspace.refetch(); void versionQuery.refetch() }}>Retry</Button></PageShell>
  if (!draft || !workspace.data || (id && !version)) return <PageShell title="Public Assay Catalog"><AppLoader label="Loading catalog" /></PageShell>
  const data = workspace.data
  const displayedCatalog = snapshot?.catalog || draft
  const busy = mutation.isPending
  const editors = version?.content_editors || []
  const username = access.data?.username
  const independent = !editors.includes(username || "")
  const order = [...new Set([...draft.layout.order, ...Object.keys(draft.modalities)])].filter((key) => draft.modalities[key])
  return <PageShell className="rounded-lg bg-background" title="Public Assay Catalog" eyebrow="Administration" actions={<>
    <input aria-label="Import catalog file" ref={upload} type="file" accept=".json,application/json" className="hidden" onChange={importFile} />
    <Button variant="outline" disabled={busy || dirty || !allowed("catalog:draft")} onClick={() => upload.current?.click()}><FileUp /> Import draft</Button>
    <Button variant="outline" onClick={() => downloadJson("assay_catalog.json", displayedCatalog)}><Download /> Export catalog</Button>
    {section && displayedCatalog.modalities[section] && <Button variant="outline" onClick={() => downloadJson(`catalog_${section}.json`, {
      kind: "coyote3.public_assay_catalog_modality", schema_version: 1, modality: section,
      definition: displayedCatalog.modalities[section],
    })}><Download /> Export section</Button>}
    {!id && <Button disabled={busy || !allowed("catalog:draft")} onClick={() => mutation.mutate({ action: "create" })}><Edit /> {data.has_published ? "Edit published catalog" : "Create first draft"}</Button>}
    {version?.status === "rejected" && <Button disabled={busy || !allowed("catalog:draft")} onClick={() => mutation.mutate({ action: "import", document: version.catalog })}><Plus /> Revise as new draft</Button>}
    {editable && !snapshot && <><Button variant="outline" disabled={busy} onClick={() => setEditing(!editing)}>{editing ? <Eye /> : <Edit />}{editing ? "Preview changes" : "Edit draft"}</Button>
      <Button disabled={!dirty || busy} onClick={() => mutation.mutate({ action: "save" })}><Save /> Save draft</Button></>}
  </>}>
    <div className="grid gap-3 rounded-lg border border-border bg-card text-card-foreground lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="space-y-4 border-r border-border p-3">
        <Button className="w-full" variant={!id ? "default" : "outline"} onClick={() => select("")}>Published catalog {data.has_published ? `v${data.catalog.version}` : ""}</Button>
        <div className="max-h-64 space-y-1 overflow-auto">
          {data.items.map((item) => <button key={item._id} onClick={() => select(item._id)}
            className={`w-full rounded-md px-2 py-2 text-left type-body-sm ${id === item._id ? "bg-primary/10" : "hover:bg-muted"}`}>
            <span className="block font-semibold">{item.content_version ? `Version ${item.content_version}` : `Draft by ${item.created_by}`}</span>
            <span>{item.status} · r{item.revision}</span>
          </button>)}
        </div>
        {editing && editable && <nav aria-label="Catalog structure" className="space-y-2">
          <Button size="sm" variant="outline" onClick={() => { setSection(""); setEntry("") }}>Introduction</Button>
          {order.map((key) => <div key={key}>
            <button className={`w-full rounded-md p-2 text-left font-semibold type-body ${section === key ? "bg-primary/10" : "hover:bg-muted"}`}
              onClick={() => { setSection(key); setEntry("") }}>{draft.modalities[key].label || key}</button>
            {section === key && Object.entries(draft.modalities[key].categories).map(([categoryKey, category]) =>
              <button key={categoryKey} className={`ml-2 block w-[calc(100%-0.5rem)] rounded-md p-2 text-left type-body-sm ${entry === categoryKey ? "bg-muted" : "hover:bg-muted"}`}
                onClick={() => setEntry(categoryKey)}>{category.label || "New entry"}</button>)}
          </div>)}
          {editing && editable && <Button size="sm" variant="outline" onClick={() => {
            const key = `section_${crypto.randomUUID().replaceAll("-", "_")}`
            setDraft({ ...draft, layout: { order: [...order, key] },
              modalities: { ...draft.modalities, [key]: { label: "New section", categories: {} } } })
            setSection(key); setEntry("")
          }}><Plus /> Add section</Button>}
        </nav>}
      </aside>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/35 p-3">
          <Badge variant="outline">{id ? version?.status : data.has_published ? "Published" : "Unpublished"}</Badge>
          {version && <span className="type-body-sm">Revision {version.revision} · Created by {version.created_by}</span>}
          {dirty && <span className="type-body-sm text-warn">Unsaved changes</span>}
        </div>
        {editing && editable ? <fieldset disabled={busy} className="min-w-0">
          <CatalogBuilder catalog={draft} section={section} entryKey={entry} workspace={data} onChange={setDraft} />
        </fieldset> : <CatalogPreview catalog={displayedCatalog} />}
        {version && <section className="space-y-3 border-t border-border bg-muted/20 p-4">
          <h2 className="type-body font-semibold">Review and publication</h2>
          {snapshot && <p role="status" className="type-body font-semibold">Viewing historical revision {snapshot.revision}. Return to the current revision to continue the workflow.</p>}
          {!snapshot && version.status === "draft" && allowed("catalog:submit") && <div className="flex flex-wrap gap-2">
            <select aria-label="Catalog reviewer" className="paper-inset rounded-lg p-2 type-body" value={reviewer} onChange={(e) => setReviewer(e.target.value)}>
              <option value="">Select reviewer</option>
              {data.reviewers.filter((v) => !editors.includes(v.username) && v.username !== username).map((v) => <option key={v.username} value={v.username}>{v.name}</option>)}
            </select>
            <Button disabled={dirty || busy || !reviewer || editing} onClick={() => mutation.mutate({ action: "submit" })}><Send /> Send for approval</Button>
          </div>}
          {!snapshot && version.status === "submitted" && allowed("catalog:review") && independent && version.review.reviewer === username && <div className="space-y-2">
            <textarea aria-label="Review reason" className="paper-inset w-full rounded-lg p-2 type-body" value={reason} onChange={(e) => setReason(e.target.value)} />
            <select aria-label="Catalog publisher" className="paper-inset rounded-lg p-2 type-body" value={publisher} onChange={(e) => setPublisher(e.target.value)}>
              <option value="">Select publisher</option>
              {data.publishers.filter((v) => !editors.includes(v.username)).map((v) => <option key={v.username} value={v.username}>{v.name}</option>)}
            </select>
            <div className="flex gap-2"><Button disabled={busy || !publisher} onClick={() => mutation.mutate({ action: "review" })}><Check /> Approve</Button>
              <Button variant="outline" disabled={busy || !reason.trim()} onClick={() => mutation.mutate({ action: "reject" })}><X /> Reject</Button></div>
          </div>}
          {!snapshot && version.status === "approved" && independent && allowed("catalog:publish") && version.review.publisher === username &&
            <Button disabled={busy} onClick={() => setConfirmPublish(true)}>Publish catalog</Button>}
          <div className="type-body-sm">Reviewer: {version.review.reviewer || "Unassigned"} · Publisher: {version.review.publisher || "Unassigned"}</div>
          {version.review.reviewer_reason && <p className="type-body-sm">{version.review.reviewer_reason}</p>}
          <details><summary className="cursor-pointer type-body font-semibold">Lifecycle history</summary>
            <ol className="mt-2 space-y-2">{version.lifecycle.map((event, index) => <li key={index} className="type-body-sm">{event.action} · {event.actor} · {new Date(event.occurred_at).toLocaleString()}{event.reason && <p>{event.reason}</p>}</li>)}</ol>
          </details>
          <details onToggle={(e) => setHistoryOpen(e.currentTarget.open)}><summary className="cursor-pointer type-body font-semibold">Revision snapshots</summary>
            {history.data?.map((item) => <Button key={item.revision} disabled={busy || dirty} size="sm" variant="outline" onClick={() => { setSnapshot(item.document); setEditing(false) }}>Preview r{item.revision}</Button>)}
            {snapshot && <Button size="sm" variant="outline" onClick={() => setSnapshot(null)}>Return to current revision</Button>}
          </details>
        </section>}
      </div>
    </div>
    <ConfirmationDialog open={confirmPublish} title="Publish catalog?" description="The approved catalog will become publicly visible." confirmLabel="Publish"
      isPending={busy} onConfirm={() => mutation.mutate({ action: "publish" })} onCancel={() => setConfirmPublish(false)} />
    <ConfirmationDialog open={pendingSelection !== null} title="Discard unsaved changes?" description="Your saved draft will remain available."
      confirmLabel="Discard changes" onConfirm={() => { setDraft(original ? structuredClone(original) : null); setParams(pendingSelection ? { version: pendingSelection } : {}); setEditing(false); setPendingSelection(null) }} onCancel={() => setPendingSelection(null)} />
  </PageShell>
}
