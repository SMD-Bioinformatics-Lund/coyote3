import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { icon } from "@/lib/assets"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { ValueBadge } from "./resource-list"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { DocumentEditorNotice } from "@/components/admin/DocumentEditorNotice"
import { downloadJson } from "@/lib/json-download"
import { configurationContent, configurationWithMetadata } from "@/lib/configuration-transfer"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { RecordProvenance } from "./RecordProvenance"
import { CatalogBuilder } from "./CatalogBuilder"
import type { Catalog, Version, Workspace } from "./catalog-types"
import { CatalogPreview } from "./CatalogPreview"
import { CatalogTree } from "../catalog/CatalogTree"
import { addCatalogChild, addCatalogParentDefaults, catalogEditorNavigation, type CatalogEditorTarget } from "./catalog-editor-navigation"
import { CatalogParentDefaults } from "./CatalogParentDefaults"
import { catalogPriceIssue } from "./useCatalogDraftPreview"

export function PublicAssayCatalogPage() {
  const access = useCurrentUserAccess()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const id = params.get("version") || ""
  const [draft, setDraft] = useState<Catalog | null>(null)
  const [section, setSection] = useState("")
  const [entry, setEntry] = useState("")
  const [editorNodeId, setEditorNodeId] = useState("")
  const [editing, setEditing] = useState(false)
  const [reviewer, setReviewer] = useState("")
  const [publisher, setPublisher] = useState("")
  const [reason, setReason] = useState("")
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [retiredOpen, setRetiredOpen] = useState(false)
  const [addParent, setAddParent] = useState("")
  const [addSource, setAddSource] = useState("")
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
    queryFn: ({ signal }) => api.get<Version>(`/admin/assay-catalog/versions/${id}`, { signal }).then((r) => r.data),
    enabled: Boolean(id) && allowed("catalog:view"),
    refetchOnWindowFocus: false,
  })
  const version = id ? versionQuery.data : undefined
  const deletion = useMutation({
    mutationFn: async () => {
      await Promise.all([
        qc.cancelQueries({ queryKey: ["catalog-version", id] }),
        qc.cancelQueries({ queryKey: ["catalog-history", id] }),
      ])
      return api.delete(`/admin/assay-catalog/versions/${id}?revision=${version!.revision}`, documentEditor.options())
    },
    onSuccess: () => {
      setConfirmDelete(false); setParams({}, { replace: true }); setDraft(null); setEditing(false)
      // Active observers detach after navigation; removing them now would trigger a new GET.
      qc.removeQueries({ queryKey: ["catalog-version", id], type: "inactive" })
      qc.removeQueries({ queryKey: ["catalog-history", id], type: "inactive" })
      void qc.invalidateQueries({ queryKey: ["admin-public-assay-catalog"] })
      notifySuccess("Unpublished catalog version deleted", "", "Catalog")
    },
    onError: (error) => notifyActionError("Catalog deletion failed", error, "Catalog"),
  })
  const original = id ? version?.catalog : workspace.data?.catalog
  const editorNodes = useMemo(() => catalogEditorNavigation(draft, workspace.data?.sources), [draft, workspace.data?.sources])
  const selectedEditorNode = editorNodes.find(node => editorNodeId ? node.node_id === editorNodeId
    : node.target?.section === section && node.target.entry === entry)
  const selectEditorTarget = (target: CatalogEditorTarget) => {
    setSection(target.section); setEntry(target.entry); setEditorNodeId("")
  }
  const addUnderNode = (nodeId: string, sourceSection?: string) => {
    if (!draft) return
    const node = editorNodes.find(item => item.node_id === nodeId)
    if (!node) return
    if (node.target) {
      const result = addCatalogChild(draft, node.target, "entry")
      setDraft(result.catalog); selectEditorTarget(result.target)
      return
    }
    const sections = [...new Set(node.offerings.map(item => item.section))]
    if (sections.length > 1 && !sourceSection) { setAddParent(nodeId); setAddSource(""); return }
    const section = sourceSection || sections[0]
    if (!section || !sections.includes(section)) return
    const parent = node.level === "modality" ? { catalog: draft, target: { section, entry: "" } }
      : addCatalogParentDefaults(draft, { ...node, offerings: node.offerings.filter(item => item.section === section) }, editorNodes)
    const result = addCatalogChild(parent.catalog, parent.target, "entry")
    setDraft(result.catalog); selectEditorTarget(result.target); setAddParent("")
  }
  useEffect(() => { setDraft(original ? structuredClone(original) : null) }, [original])
  const dirty = Boolean(draft && original && JSON.stringify(draft) !== JSON.stringify(original))
  const documentEditor = useDocumentEditor("assay-catalog", id, Boolean(version?.status === "draft" && !version.system_installed && allowed("catalog:draft")))
  const editable = documentEditor.owned && Boolean(version?.status === "draft" && !version.system_installed && allowed("catalog:draft"))
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
    setEditing(Boolean(workspace.data?.items.find(item => item._id === oid)?.status === "draft")); setReviewer(""); setPublisher(""); setReason(""); setEditorNodeId(""); setSection(""); setEntry("")
  }
  const mutation = useMutation({
    mutationFn: async ({ action, document }: { action: string; document?: unknown }) => {
      const base = "/admin/assay-catalog"
      if (action === "create") return (await api.post<Version>(`${base}/drafts`)).data
      if (action === "import") return (await api.post<Version>(`${base}/imports`, { document })).data
      if (action === "save") return (await api.patch<Version>(`${base}/drafts/${id}`,
        { revision: version?.revision, catalog: draft }, documentEditor.options())).data
      return (await api.post<Version>(`${base}/drafts/${id}/${action === "reject" ? "review" : action}`,
        { revision: version?.revision, assignee: action === "submit" ? reviewer : publisher,
          approve: action !== "reject", reason }, documentEditor.options())).data
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
    try { mutation.mutate({ action: "import", document: configurationContent(JSON.parse(await file.text())) }) }
    catch (error) { notifyActionError("Invalid catalog JSON", error, "Catalog") }
  }
  const [historyOpen, setHistoryOpen] = useState(false)
  const history = useQuery({
    queryKey: ["catalog-history", id, version?.revision],
    queryFn: ({ signal }) => api.get<{ items: { revision: number; document: Version }[] }>(
      `/admin/assay-catalog/versions/${id}/revisions`, { signal }).then((r) => r.data.items),
    enabled: Boolean(id) && historyOpen && allowed("catalog:view"),
  })
  const [snapshot, setSnapshot] = useState<Version | null>(null)
  const [includeMetadata, setIncludeMetadata] = useState(false)
  useEffect(() => { setSnapshot(null) }, [id, version?.revision])
  if (access.isLoading) return <PageShell title="Assay Catalog"><AppLoader label="Loading permissions" /></PageShell>
  if (!allowed("catalog:view")) return <PageShell title="Assay Catalog"><p>Catalog access is required.</p></PageShell>
  if (workspace.isError || (id && versionQuery.isError)) return <PageShell title="Assay Catalog"><p role="alert">The catalog could not be loaded.</p><Button onClick={() => { void workspace.refetch(); if (id) void versionQuery.refetch() }}>Retry</Button></PageShell>
  if (!draft || !workspace.data || (id && !version)) return <PageShell title="Assay Catalog"><AppLoader label="Loading catalog" /></PageShell>
  const data = workspace.data
  const displayedCatalog = snapshot?.catalog || draft
  const exportContent = (content: unknown) => includeMetadata
    ? configurationWithMetadata(configurationContent(content), { ...displayedCatalog, ...(snapshot || version) })
    : configurationContent(content)
  const busy = mutation.isPending || deletion.isPending
  const priceIssue = catalogPriceIssue(draft)
  const editors = version?.content_editors || []
  const username = access.data?.username
  const independent = !editors.includes(username || "")
  const order = [...new Set([...draft.layout.order, ...Object.keys(draft.modalities)])].filter((key) => draft.modalities[key])
  return <PageShell className="flex-1" title="Assay Catalog" eyebrow="Administration" actions={<div className="flex flex-wrap items-center gap-2">
    {version?.status === "rejected" && <Button disabled={busy || !allowed("catalog:draft")} onClick={() => mutation.mutate({ action: "import", document: version.catalog })}><icon.plus /> Revise as new draft</Button>}
    {editable && !snapshot && <><Button variant="outline" disabled={busy} onClick={() => setEditing(!editing)}>{editing ? <icon.eye /> : <icon.edit />}{editing ? "Preview changes" : "Edit draft"}</Button>
      <Button disabled={!dirty || busy || Boolean(priceIssue)} title={priceIssue}
        onClick={() => mutation.mutate({ action: "save" })}><icon.save /> Save draft</Button></>}
  </div>}>
    <DocumentEditorNotice editor={documentEditor} />
    <div className="grid flex-1 gap-3 rounded-lg border border-border bg-card text-card-foreground lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="space-y-4 border-b border-border p-3 lg:border-b-0 lg:border-r">
        <Button className="w-full" variant={!id ? "default" : "outline"} onClick={() => select("")}>{data.has_published ? `Published catalog v${data.catalog.version}` : "Starter catalog"}</Button>
        {!id && <div className="space-y-2">
          <Button className="w-full whitespace-normal" disabled={busy || !allowed("catalog:draft")} onClick={() => mutation.mutate({ action: "create" })}><icon.edit /> {data.has_published ? "Edit published catalog" : "Create first draft"}</Button>
          <p className="type-body-sm text-muted-foreground">Organize DNA and RNA sections into families, groups and assay or diagnosis entries. Starter folders are optional.</p>
        </div>}
        <div className="max-h-64 space-y-1 overflow-auto">
          {data.items.filter(item => retiredOpen ? item.status === "published" && item.content_version !== data.catalog.version : item.status !== "published" || item.content_version === data.catalog.version).map((item) => <button key={item._id} onClick={() => select(item._id)}
            className={`w-full rounded-md px-2 py-2 text-left type-body-sm ${id === item._id ? "bg-primary/10" : "hover:bg-muted"}`}>
            <span className="block font-semibold">{item.content_version ? `Version ${item.content_version}` : `Draft by ${item.created_by}`}</span>
            <span className="flex flex-wrap items-center gap-2"><ValueBadge kind="status" value={item.status === "published" && item.content_version !== data.catalog.version ? "retired" : item.status} />r{item.revision}</span>
          </button>)}
        </div>
        <Button variant="outline" size="sm" aria-expanded={retiredOpen} onClick={() => setRetiredOpen(!retiredOpen)}><icon.history />{retiredOpen ? "Hide retired versions" : "Browse retired versions"}</Button>
        {data.items.some(item => item.status === "draft" && !item.system_installed) && allowed("catalog:draft") &&
          <p className="type-meta text-muted-foreground">Select a draft to edit or delete it. Published versions are retained.</p>}
        <details className="space-y-2">
          <summary className="cursor-pointer type-body-sm font-semibold">Import and export</summary>
          <div className="flex flex-col items-start gap-2 pt-2">
    <input aria-label="Import catalog file" ref={upload} type="file" accept=".json,application/json" className="hidden" onChange={importFile} />
    <Button variant="outline" disabled={busy || dirty || !allowed("catalog:draft")} onClick={() => upload.current?.click()}><icon.fileUp /> Import draft</Button>
    <label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={includeMetadata} onChange={event => setIncludeMetadata(event.target.checked)} />Include metadata</label>
    <Button variant="outline" onClick={() => downloadJson("assay_catalog.json", exportContent(displayedCatalog))}><icon.download /> Export catalog</Button>
    {section && displayedCatalog.modalities[section] && <Button variant="outline" onClick={() => downloadJson(`catalog_${section}.json`, exportContent({
      kind: "coyote3.public_assay_catalog_modality", schema_version: 1, modality: section,
      definition: displayedCatalog.modalities[section],
    }))}><icon.download /> Export section</Button>}

          </div>
        </details>
        {editing && editable && <nav aria-label="Catalog structure" className="space-y-2">
          <Button size="sm" variant="outline" onClick={() => {
            const key = `section_${crypto.randomUUID().replaceAll("-", "_")}`
            setDraft({ ...draft, layout: { order: [...order, key] },
              modalities: { ...draft.modalities, [key]: { label: "New section", categories: {} } } })
            selectEditorTarget({ section: key, entry: "" })
          }}><icon.plus /> Add section</Button>
          <Button size="sm" variant="outline" onClick={() => selectEditorTarget({ section: "", entry: "" })}>Introduction</Button>
          <nav aria-label="Catalog levels"><CatalogTree categories={Object.fromEntries(editorNodes.map(node => [node.node_id, {
            label: node.label, parent_key: node.parent_id,
          }]))} selected={selectedEditorNode?.node_id} defaultExpanded={['["dna"]', '["rna"]']}
            appearances={Object.fromEntries(editorNodes.map(node => [node.node_id, { level: node.level,
              tone: node.level === "modality" ? node.offerings[0]?.modality : node.level === "family"
                ? node.offerings[0]?.family : node.level === "group" ? node.offerings[0]?.group_id : undefined,
            }]))} onAdd={addUnderNode}
            onSelect={nodeId => {
              const node = editorNodes.find(item => item.node_id === nodeId)
              if (node?.target) selectEditorTarget(node.target)
              else setEditorNodeId(nodeId)
            }} /></nav>
        </nav>}
      </aside>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/35 p-3">
          <ValueBadge kind="status" value={id ? version?.status ?? "" : data.has_published ? "Published" : "Unpublished"} />
          {version && <><span className="type-body-sm">Revision {version.revision}</span>
            <div className="flex items-center gap-2 type-meta text-muted-foreground">Created by <RecordProvenance record={version} /></div>
            <span className="type-meta text-muted-foreground">Updated by {version.updated_by || "Unknown"}</span></>}
          {dirty && <span className="type-body-sm text-warn">Unsaved changes</span>}
        </div>
        {version && <section className="surface-panel space-y-3 p-4" aria-label="Review and publication">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="type-section-title">Review and publication</h2>
            {!snapshot && !version.system_installed && ["draft", "submitted", "approved", "rejected"].includes(version.status) && allowed("catalog:draft") &&
              <Button variant="destructive"
                disabled={busy || dirty || version.status === "draft" && !documentEditor.owned}
                title={dirty ? "Save or discard changes before deleting this version" : undefined}
                onClick={() => setConfirmDelete(true)}><icon.trash2 /> {version.status === "draft" ? "Delete draft" : "Delete unpublished version"}</Button>}
          </div>
          <ol aria-label="Publication steps" className="flex flex-wrap gap-4 type-body-sm">
            {["Edit draft", "Independent review", "Publish"].map((label, index) => {
              const current = version.status === "draft" || version.status === "rejected" ? 0 : version.status === "submitted" ? 1 : 2
              return <li key={label} aria-current={index === current ? "step" : undefined}
                className={index === current ? "font-semibold text-primary" : "text-muted-foreground"}>{index + 1}. {label}</li>
            })}
          </ol>
          <p className="type-body-sm text-muted-foreground">
            {version.status === "draft" ? dirty
              ? "Save your changes, then preview the catalog before sending it to an independent reviewer."
              : editing ? "Edit the catalog using the tree, then choose Preview changes to check the public view before sending for approval."
              : "Check the preview, select an independent reviewer and send the saved draft for approval."
              : version.status === "submitted" ? `Waiting for review by ${version.review.reviewer || "the assigned reviewer"}. The assigned reviewer can approve or return it with a reason.`
              : version.status === "approved" ? `Approved for publication by ${version.review.publisher || "the assigned publisher"}. Only the assigned independent publisher can publish this version.`
              : version.status === "rejected" ? "The reviewer returned this version. Choose Revise as new draft to make changes."
              : "This version is published. Create a separate draft to make changes."}
          </p>
          {snapshot && <p role="status" className="type-body font-semibold">Viewing historical revision {snapshot.revision}. Return to the current revision to continue the workflow.</p>}
          {!snapshot && !version.system_installed && version.status === "draft" && allowed("catalog:submit") && <div className="flex flex-wrap gap-2">
            <select aria-label="Catalog reviewer" className="paper-inset rounded-lg p-2 type-body" value={reviewer} onChange={(e) => setReviewer(e.target.value)}>
              <option value="">Select reviewer</option>
              {data.reviewers.filter((v) => !editors.includes(v.username) && v.username !== username).map((v) => <option key={v.username} value={v.username}>{v.name}</option>)}
            </select>
            <Button disabled={dirty || busy || !reviewer || editing} onClick={() => mutation.mutate({ action: "submit" })}><icon.send /> Send for approval</Button>
          </div>}
          {!snapshot && !version.system_installed && version.status === "submitted" && allowed("catalog:review") && independent && version.review.reviewer === username && <div className="space-y-2">
            <textarea aria-label="Review reason" className="paper-inset w-full rounded-lg p-2 type-body" value={reason} onChange={(e) => setReason(e.target.value)} />
            <select aria-label="Catalog publisher" className="paper-inset rounded-lg p-2 type-body" value={publisher} onChange={(e) => setPublisher(e.target.value)}>
              <option value="">Select publisher</option>
              {data.publishers.filter((v) => !editors.includes(v.username)).map((v) => <option key={v.username} value={v.username}>{v.name}</option>)}
            </select>
            <div className="flex gap-2"><Button disabled={busy || !publisher} onClick={() => mutation.mutate({ action: "review" })}><icon.check /> Approve</Button>
              <Button variant="outline" disabled={busy || !reason.trim()} onClick={() => mutation.mutate({ action: "reject" })}><icon.x /> Reject</Button></div>
          </div>}
          {!snapshot && !version.system_installed && version.status === "approved" && independent && allowed("catalog:publish") && version.review.publisher === username &&
            <Button disabled={busy} onClick={() => setConfirmPublish(true)}>Publish catalog</Button>}
          <div className="type-body-sm">Reviewer: {version.review.reviewer || "Unassigned"} · Publisher: {version.review.publisher || "Unassigned"}</div>
          {version.review.reviewer_reason && <p className="type-body-sm">{version.review.reviewer_reason}</p>}
          <details>
            <summary className="cursor-pointer type-body-sm font-semibold">History and version options</summary>
            <div className="space-y-3 pt-3">
          <details><summary className="cursor-pointer type-body font-semibold">Lifecycle history</summary>
            <ol className="mt-2 space-y-2">{version.lifecycle.map((event, index) => <li key={index} className="type-body-sm">{event.action} · {event.actor} · {new Date(event.occurred_at).toLocaleString()}{event.reason && <p>{event.reason}</p>}</li>)}</ol>
          </details>
          <details onToggle={(e) => setHistoryOpen(e.currentTarget.open)}><summary className="cursor-pointer type-body font-semibold">Revision snapshots</summary>
            {history.data?.map((item) => <Button key={item.revision} disabled={busy || dirty} size="sm" variant="outline" onClick={() => { setSnapshot(item.document); setEditing(false) }}>Preview r{item.revision}</Button>)}
            {snapshot && <Button size="sm" variant="outline" onClick={() => setSnapshot(null)}>Return to current revision</Button>}
          </details>

            </div>
          </details>
        </section>}
        {editing && editable ? <fieldset disabled={busy} className="min-w-0">
          {selectedEditorNode && !selectedEditorNode.target ? <CatalogParentDefaults key={selectedEditorNode.node_id} node={selectedEditorNode} catalog={draft}
            onSelect={selectEditorTarget} onAdd={() => {
              const result = addCatalogParentDefaults(draft, selectedEditorNode, editorNodes)
              setDraft(result.catalog); selectEditorTarget(result.target)
            }} onAddChild={(section, kind) => {
              const parent = selectedEditorNode.level === "modality" ? { catalog: draft, target: { section, entry: "" } }
                : addCatalogParentDefaults(draft, { ...selectedEditorNode,
                  offerings: selectedEditorNode.offerings.filter(item => item.section === section) }, editorNodes)
              const result = addCatalogChild(parent.catalog, parent.target, kind)
              setDraft(result.catalog); selectEditorTarget(result.target)
            }} /> : <CatalogBuilder key={`${section}:${entry}`} catalog={draft} section={section} entryKey={entry}
              workspace={data} onChange={setDraft} onSelectEntry={key => selectEditorTarget({ section, entry: key })} />}
        </fieldset> : <CatalogPreview catalog={displayedCatalog} />}

      </div>
    </div>
    <ConfirmationDialog open={confirmDelete} title="Delete unpublished catalog version?" description="The selected version and its private snapshots will be removed. The published catalog is preserved and an audit receipt is retained." confirmLabel="Delete version" isPending={deletion.isPending} onConfirm={() => deletion.mutate()} onCancel={() => setConfirmDelete(false)} />
    <ConfirmationDialog open={Boolean(addParent)} title="Add new entry" confirmLabel="Add entry" confirmDisabled={!addSource}
      description={<label className="grid gap-2 type-body-sm">Choose the parent section
        <select aria-label="Parent section for new entry" className="form-control rounded-lg p-2 type-body"
          value={addSource} onChange={event => setAddSource(event.target.value)}>
          <option value="">Select section</option>
          {[...new Set(editorNodes.find(node => node.node_id === addParent)?.offerings.map(item => item.section) || [])]
            .map(key => <option key={key} value={key}>{draft.modalities[key].label || key}</option>)}
        </select>
      </label>} onConfirm={() => addUnderNode(addParent, addSource)} onCancel={() => setAddParent("")} />
    <ConfirmationDialog open={confirmPublish} title="Publish catalog?" description="The approved catalog will become publicly visible." confirmLabel="Publish"
      isPending={busy} onConfirm={() => mutation.mutate({ action: "publish" })} onCancel={() => setConfirmPublish(false)} />
    <ConfirmationDialog open={pendingSelection !== null} title="Discard unsaved changes?" description="Your saved draft will remain available."
      confirmLabel="Discard changes" onConfirm={() => { setDraft(original ? structuredClone(original) : null); setParams(pendingSelection ? { version: pendingSelection } : {}); setEditing(false); setPendingSelection(null) }} onCancel={() => setPendingSelection(null)} />
  </PageShell>
}
