import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Input } from "@/components/ui/input"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Beaker,
  Check,
  CirclePlus,
  CopyPlus,
  Download,
  FileCheck2,
  GitCompareArrows,
  History,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Save,
  Search,
  Send,
  ShieldCheck,
  Trash2
} from "lucide-react"
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { Link } from "react-router-dom"
import { ANALYSES, clone, emptyRuleSetScope, generatedRuleSetName, newRule, newRuleBlock, type CreationMode, type NewRuleSetScope } from "./clinical-rule-authoring"
import type {
  ClinicalRuleAssayOption,
  ClinicalRuleReviewerOption,
  ClinicalRuleRevision,
  ClinicalRuleSet,
  FactDefinition,
  RuleBlock
} from "./clinical-rules-types"
import {
  CLINICAL_RULE_STATUS_LABELS,
  clinicalRuleSectionTone
} from "./clinical-rules-visuals"
import { ClinicalRuleStatusBadge } from "./ClinicalRuleStatusBadge"
import { outputPreview } from "./rule-output-preview"
import { storedWidth } from "./rule-workspace-storage"
import { RuleEditor } from "./RuleEditor"
import { ResizeDivider } from "./RuleWorkspaceDivider"

export function ClinicalRulesPage() {
  const queryClient = useQueryClient()
  const access = useCurrentUserAccess()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<ClinicalRuleSet | null>(null)
  const [selectedBlock, setSelectedBlock] = useState(0)
  const [selectedRule, setSelectedRule] = useState(0)
  const [dirty, setDirty] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newScope, setNewScope] = useState<NewRuleSetScope>(emptyRuleSetScope)
  const [newNameEdited, setNewNameEdited] = useState(false)
  const [creationMode, setCreationMode] = useState<CreationMode>("blank")
  const [templateId, setTemplateId] = useState("")
  const [importDocument, setImportDocument] = useState<Record<string, unknown> | null>(null)
  const [importError, setImportError] = useState("")
  const [reviewerAssignee, setReviewerAssignee] = useState("")
  const [publisherAssignee, setPublisherAssignee] = useState("")
  const [ruleListCollapsed, setRuleListCollapsed] = useState(false)
  const [sectionsCollapsed, setSectionsCollapsed] = useState(false)
  const [ruleListWidth, setRuleListWidth] = useState(() => storedWidth("clinical-rules-width:Resize rule-set list", 272))
  const [sectionsWidth, setSectionsWidth] = useState(() => storedWidth("clinical-rules-width:Resize report sections", 208))
  const [previewWidth, setPreviewWidth] = useState(() => storedWidth("clinical-rules-width:Resize text preview", 380))
  const [historyOpen, setHistoryOpen] = useState(false)
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null)
  const [deleteDraftOpen, setDeleteDraftOpen] = useState(false)
  const editGeneration = useRef(0)

  const listQuery = useQuery({ queryKey: ["clinical-rule-sets", search, status], queryFn: () => api.get<{ items: ClinicalRuleSet[] }>(`/admin/clinical-rule-sets?q=${encodeURIComponent(search)}${status ? `&status=${status}` : ""}`).then((response) => response.data) })
  const templateQuery = useQuery({ queryKey: ["clinical-rule-templates"], enabled: creating, queryFn: () => api.get<{ items: ClinicalRuleSet[] }>("/admin/clinical-rule-sets?status=published&per_page=200").then((response) => response.data) })
  const factsQuery = useQuery({ queryKey: ["clinical-rule-facts"], queryFn: () => api.get<{ items: FactDefinition[] }>("/admin/clinical-rule-sets/facts").then((response) => response.data) })
  const optionsQuery = useQuery({ queryKey: ["clinical-rule-authoring-options"], queryFn: () => api.get<{ assays: ClinicalRuleAssayOption[]; condition_values: Record<string, string[]>; clinical_reviewers: ClinicalRuleReviewerOption[]; publishers: ClinicalRuleReviewerOption[] }>("/admin/clinical-rule-sets/authoring-options").then((response) => response.data) })
  const versionQuery = useQuery({ queryKey: ["clinical-rule-set", selectedId], enabled: Boolean(selectedId), queryFn: () => api.get<ClinicalRuleSet>(`/admin/clinical-rule-sets/versions/${selectedId}`).then((response) => response.data) })
  const revisionsQuery = useQuery({ queryKey: ["clinical-rule-revisions", selectedId], enabled: Boolean(selectedId) && historyOpen, queryFn: () => api.get<{ items: ClinicalRuleRevision[] }>(`/admin/clinical-rule-sets/versions/${selectedId}/revisions`).then((response) => response.data) })
  useEffect(() => {
    if (selectedId && versionQuery.data?._id === selectedId) {
      setDraft(clone(versionQuery.data))
      setDirty(false)
      setSelectedBlock(0)
      setSelectedRule(0)
      setSelectedRevision(null)
    }
  }, [selectedId, versionQuery.data])
  const facts = useMemo(() => factsQuery.data?.items || [], [factsQuery.data?.items])
  const controlledValues = useMemo(() => optionsQuery.data?.condition_values || {}, [optionsQuery.data?.condition_values])

  const saveMutation = useMutation({
    mutationFn: ({ document, generation }: { document: ClinicalRuleSet; generation: number }) => api.patch<ClinicalRuleSet>(`/admin/clinical-rule-sets/drafts/${document._id}`, { revision: document.revision, name: document.name, analysis_declarations: document.analysis_declarations, terminology: document.terminology, blocks: document.blocks, test_cases: document.test_cases, references: document.references, change_summary: document.change_summary }).then((response) => ({ document: response.data, generation })),
    onSuccess: ({ document, generation }) => { setDraft((current) => generation === editGeneration.current ? clone(document) : current ? { ...current, revision: document.revision } : current); if (generation === editGeneration.current) setDirty(false); queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] }); queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] }) },
  })
  const saveDraft = saveMutation.mutate
  const savePending = saveMutation.isPending
  useEffect(() => {
    if (!dirty || draft?.status !== "draft" || savePending) return
    const generation = editGeneration.current
    const timer = window.setTimeout(() => saveDraft({ document: draft, generation }), 800)
    return () => window.clearTimeout(timer)
  }, [dirty, draft, saveDraft, savePending])

  const mutateDraft = (change: (document: ClinicalRuleSet) => void) => {
    if (!hasPermission(access.data, "clinical_rules:draft")) return
    setDraft((current) => { if (!current || current.status !== "draft") return current; const next = clone(current); change(next); return next })
    editGeneration.current += 1
    setDirty(true)
  }
  const block = draft?.blocks[selectedBlock]
  const metadataOutput = !!block && ["report_header_suffix", "clinical_question"].includes(block.section)
  const rule = block?.rules[selectedRule]
  const can = (permission: string) => hasPermission(access.data, permission)
  const editableDraft = draft?.status === "draft" && can("clinical_rules:draft")
  const workflowReady = !dirty && !saveMutation.isPending

  const beginCreation = () => {
    setSelectedId(null)
    setDraft(null)
    setSelectedBlock(0)
    setSelectedRule(0)
    setNewScope(emptyRuleSetScope())
    setNewNameEdited(false)
    setCreationMode("blank")
    setTemplateId("")
    setImportDocument(null)
    setImportError("")
    setCreating(true)
    setHistoryOpen(false)
  }
  const cancelCreation = () => {
    setCreating(false)
    setNewScope(emptyRuleSetScope())
    setNewNameEdited(false)
    setImportDocument(null)
    setImportError("")
  }
  const openRuleSet = (documentId: string) => {
    if (documentId === selectedId) return
    setCreating(false)
    setDraft(null)
    setSelectedBlock(0)
    setSelectedRule(0)
    setSelectedId(documentId)
    setHistoryOpen(false)
    setSelectedRevision(null)
  }

  const actionMutation = useMutation({ mutationFn: ({ path, body = {} }: { path: string; body?: Record<string, unknown> }) => api.post<ClinicalRuleSet>(path, body).then((response) => response.data), onSuccess: (document) => {
    setSelectedId(document._id); setDraft(clone(document)); setDirty(false); setCreating(false)
    void queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] })
    void queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] })
    if (document.status === "published" || document.status === "retired") {
      void queryClient.invalidateQueries({ queryKey: ["report-preview"] })
      void queryClient.invalidateQueries({ queryKey: ["admin-resource-context", "aspc"] })
      void queryClient.invalidateQueries({ queryKey: ["assay-setup-context"] })
    }
  } })
  const deleteDraftMutation = useMutation({
    mutationFn: ({ documentId, revision }: { documentId: string; revision: number }) => api.delete(`/admin/clinical-rule-sets/drafts/${documentId}?revision=${revision}`),
    onSuccess: (_, { documentId }) => {
      setDeleteDraftOpen(false)
      setSelectedId(null)
      setDraft(null)
      setDirty(false)
      setHistoryOpen(false)
      queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] })
      queryClient.removeQueries({ queryKey: ["clinical-rule-set", documentId] })
      queryClient.removeQueries({ queryKey: ["clinical-rule-revisions", documentId] })
    },
  })
  const createRevision = () => draft && actionMutation.mutate({ path: "/admin/clinical-rule-sets/drafts", body: { source_version_id: draft._id, source: "template" } })
  const createRuleSet = () => {
    const scope = { asp_id: newScope.asp_id.trim(), subpanel_id: newScope.subpanel_id.trim(), analyte: newScope.analyte, language: newScope.language.trim() }
    if (creationMode === "import" && importDocument) {
      actionMutation.mutate({ path: "/admin/clinical-rule-sets/imports", body: { document: importDocument, scope, name: newScope.name.trim() } })
      return
    }
    actionMutation.mutate({ path: "/admin/clinical-rule-sets/drafts", body: creationMode === "template" ? { source_version_id: templateId, scope, name: newScope.name.trim(), source: "template" } : { scope, name: newScope.name.trim(), source: "ui" } })
  }
  const deleteDraft = () => {
    if (draft) deleteDraftMutation.mutate({ documentId: draft._id, revision: draft.revision })
  }
  const lifecycleAction = (action: string, body: Record<string, unknown> = { reason: draft?.change_summary || "Workflow transition" }) => draft && actionMutation.mutate({ path: `/admin/clinical-rule-sets/drafts/${draft._id}/${action}`, body })
  const retireRuleSet = () => draft && actionMutation.mutate({ path: `/admin/clinical-rule-sets/versions/${draft._id}/retire`, body: { reason: draft.change_summary || "Clinical rule set retired" } })

  const validationQuery = useQuery({ queryKey: ["clinical-rule-validation", draft?._id, draft?.revision], enabled: false, queryFn: () => api.post<{ valid: boolean; errors: string[]; warnings: string[] }>(`/admin/clinical-rule-sets/drafts/${draft?._id}/validate`).then((response) => response.data) })
  const selectedPreview = useMemo(() => rule ? outputPreview(rule.output, facts) : "Select a rule to preview its report text.", [rule, facts])
  const revisionItems = revisionsQuery.data?.items || []
  const historicalRevision = revisionItems.find((item) => item.revision === selectedRevision) || revisionItems[0]
  const assayTemplates = (templateQuery.data?.items || []).filter((item) => item.scope.asp_id === newScope.asp_id)
  const downloadRuleSet = async () => {
    if (!draft) return
    const exportDocument = await api.get<ClinicalRuleSet>(`/admin/clinical-rule-sets/versions/${draft._id}/export`).then((response) => response.data)
    const url = URL.createObjectURL(new Blob([JSON.stringify(exportDocument, null, 2)], { type: "application/json" }))
    const anchor = window.document.createElement("a")
    anchor.href = url
    anchor.download = `${draft.rule_set_id}_v${draft.content_version}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }
  const chooseImport = (file: File | undefined) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as Record<string, unknown>
        setImportDocument(parsed)
        setImportError("")
      } catch {
        setImportDocument(null)
        setImportError("Choose a valid clinical-rule JSON export.")
      }
    }
    reader.readAsText(file)
  }

  if (listQuery.isLoading || factsQuery.isLoading || optionsQuery.isLoading) return <PageShell eyebrow="Clinical reporting" title="Reporting Rule Sets"><AppLoader label="Loading clinical rules" /></PageShell>
  return (
    <PageShell eyebrow="Clinical reporting" title="Reporting Rule Sets" description="Author, review, validate, and publish governed report wording." actions={<>{dirty || saveMutation.isPending ? <Badge variant="outline"><Save /> {saveMutation.isPending ? "Saving" : "Unsaved"}</Badge> : draft?.status === "draft" ? <Badge variant="outline"><Check /> Saved</Badge> : null}{can("clinical_rules:test") && <Button variant="outline" nativeButton={false} render={<Link to="/admin/clinical-rules/testing" />}><Beaker /> Test rules</Button>}{can("clinical_rules:draft") && !creating && <Button variant="outline" disabled={!workflowReady} onClick={beginCreation}><Plus /> New rule set</Button>}{draft?.status !== "draft" && draft && can("clinical_rules:draft") && <Button onClick={createRevision}><CopyPlus /> Create revision</Button>}</>}>
      {creating && (
        <section className="surface-panel mb-3 p-4" aria-label="Create clinical rule set">
          <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Draft creation method">
            {(["blank", "template", "import"] as CreationMode[]).map((mode) => <Button key={mode} type="button" size="sm" variant={creationMode === mode ? "default" : "outline"} onClick={() => setCreationMode(mode)}>{mode === "blank" ? "Build in UI" : mode === "template" ? "Use template" : "Import JSON"}</Button>)}
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <label className="type-label">Assay<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={newScope.asp_id} onChange={(event) => { const assay = optionsQuery.data?.assays.find((item) => item.asp_id === event.target.value); setNewScope((current) => ({ ...current, asp_id: event.target.value, analyte: assay?.analyte || "dna", subpanel_id: "base", name: newNameEdited ? current.name : generatedRuleSetName(assay, "base") })) }}><option value="">Select assay</option>{(optionsQuery.data?.assays || []).map((assay) => <option key={assay.asp_id} value={assay.asp_id}>{assay.display_name} ({assay.asp_id})</option>)}</select></label>
            <label className="type-label">Subpanel<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={newScope.subpanel_id} onChange={(event) => { const subpanelId = event.target.value; const assay = optionsQuery.data?.assays.find((item) => item.asp_id === newScope.asp_id); setNewScope((current) => ({ ...current, subpanel_id: subpanelId, name: newNameEdited ? current.name : generatedRuleSetName(assay, subpanelId) })) }}><option value="">Select subpanel</option>{(optionsQuery.data?.assays.find((item) => item.asp_id === newScope.asp_id)?.subpanels || []).map((scope) => <option key={scope.subpanel_id} value={scope.subpanel_id}>{scope.display_name} ({scope.subpanel_id})</option>)}</select></label>
            <label className="type-label">Analyte<Input className="mt-1 uppercase" value={newScope.analyte} readOnly /></label>
            <label className="type-label">Language<Input className="mt-1" value={newScope.language} onChange={(event) => setNewScope({ ...newScope, language: event.target.value })} /></label>
            <label className="type-label">Rule-set name<Input className="mt-1" value={newScope.name} onChange={(event) => { setNewNameEdited(true); setNewScope({ ...newScope, name: event.target.value }) }} /></label>
          </div>
          {creationMode === "template" && <label className="type-label mt-3 block max-w-xl">Template rule set<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={templateId} onChange={(event) => { const selected = assayTemplates.find((item) => item._id === event.target.value); setTemplateId(event.target.value); if (selected && !newNameEdited) setNewScope((current) => ({ ...current, name: `${selected.name} - test` })) }}><option value="">Select a published {newScope.asp_id ? "assay-specific" : ""} template</option>{assayTemplates.map((item) => <option key={item._id} value={item._id}>{item.scope.subpanel_id} · {item.name} (v{item.content_version})</option>)}</select></label>}
          {creationMode === "import" && <label className="type-label mt-3 block max-w-xl">Canonical rule-set JSON<input className="mt-1 block w-full text-sm" type="file" accept="application/json,.json" onChange={(event) => chooseImport(event.target.files?.[0])} />{importDocument && <span className="mt-1 block text-xs text-pass">Valid JSON loaded. It will be validated again by the server before a draft is created.</span>}{importError && <span className="mt-1 block text-xs text-destructive">{importError}</span>}</label>}
          <div className="mt-3 flex justify-end gap-2"><Button variant="ghost" onClick={cancelCreation}>Cancel</Button><Button disabled={!newScope.asp_id.trim() || !newScope.subpanel_id.trim() || !newScope.name.trim() || actionMutation.isPending || (creationMode === "template" && !templateId) || (creationMode === "import" && !importDocument)} onClick={createRuleSet}><CirclePlus /> Create draft</Button></div>
        </section>
      )}
      <div className={cn("clinical-rules-layout clinical-rules-workspace surface-panel overflow-hidden", ruleListCollapsed && "is-rule-list-collapsed")} style={{ "--rule-list-width": `${ruleListWidth}px`, "--preview-width": `${previewWidth}px` } as CSSProperties}>
        <aside className="flex min-h-0 min-w-0 flex-col border-b border-border xl:border-b-0">
          {ruleListCollapsed ? <button type="button" className="clinical-rules-rail" aria-label="Expand rule-set list" onClick={() => setRuleListCollapsed(false)}><PanelLeftOpen /><span>Rule sets</span></button> : <>
          <div className="space-y-2 border-b border-border p-3">
            <div className="flex items-center gap-1"><div className="relative min-w-0 flex-1"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input aria-label="Search clinical rules" className="pl-8" placeholder="Search rules" value={search} onChange={(event) => setSearch(event.target.value)} /></div><Button size="icon-sm" variant="ghost" title="Collapse rule-set list" aria-label="Collapse rule-set list" onClick={() => setRuleListCollapsed(true)}><PanelLeftClose /></Button></div>
            <select className="paper-inset w-full rounded-lg p-2 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All workflow states</option>{Object.entries(CLINICAL_RULE_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          </div>
          <nav className="min-h-0 flex-1 overflow-y-auto p-2" aria-label="Clinical rule sets">
            {(listQuery.data?.items || []).map((item) => <button type="button" key={item._id} disabled={!workflowReady} className={cn("mb-1 w-full rounded-lg p-3 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60", selectedId === item._id && "bg-primary/10 ring-1 ring-primary/30")} onClick={() => openRuleSet(item._id)}><span className="block truncate text-sm font-semibold">{item.name}</span><span className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{item.scope.asp_id} · {item.scope.subpanel_id}</span><ClinicalRuleStatusBadge status={item.status} prefix={`v${item.content_version} `} /></span></button>)}
          </nav>
          </>}
        </aside>
        {!ruleListCollapsed && <ResizeDivider label="Resize rule-set list" width={ruleListWidth} setWidth={setRuleListWidth} min={210} max={440} />}
        <main className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] border-b border-border xl:border-b-0 xl:border-r">
          {!draft ? <div className="grid h-full place-items-center p-8 text-sm text-muted-foreground">Select a rule set to inspect or edit.</div> : <>
            <div className="border-b border-border bg-muted/35 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">{editableDraft ? <Input aria-label="Rule-set name" className="max-w-xl font-semibold" value={draft.name} onChange={(event) => mutateDraft((document) => { document.name = event.target.value })} /> : <h2 className="font-semibold">{draft.name}</h2>}<p className="mt-1 text-xs text-muted-foreground">{draft.rule_set_id} · version {draft.content_version} · revision {draft.revision}</p></div><div className="flex items-center gap-2">{!editableDraft && <Badge variant="outline">Read-only</Badge>}<Button size="sm" variant="outline" onClick={downloadRuleSet}><Download /> Export JSON</Button><ClinicalRuleStatusBadge status={draft.status} /></div></div>
              {editableDraft && <div className="mt-3 flex flex-wrap items-end gap-2"><Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => validationQuery.refetch()}><FileCheck2 /> Validate</Button>{can("clinical_rules:submit") && <label className="type-label">Assign clinical reviewer<select className="paper-inset mt-1 block rounded-lg p-1.5 text-xs" value={reviewerAssignee} onChange={(event) => setReviewerAssignee(event.target.value)}><option value="">Select reviewer</option>{(optionsQuery.data?.clinical_reviewers || []).map((user) => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select></label>}{can("clinical_rules:submit") && <Button size="sm" disabled={!workflowReady || !reviewerAssignee} onClick={() => lifecycleAction("submit", { reason: draft.change_summary || "Submitted for clinical review", assignee: reviewerAssignee })}><Send /> Submit</Button>}<Button size="sm" variant="destructive" disabled={!workflowReady || deleteDraftMutation.isPending} onClick={() => setDeleteDraftOpen(true)}><Trash2 /> Delete draft</Button></div>}
              {draft.status === "submitted" && can("clinical_rules:clinical_review") && <Button className="mt-3" size="sm" disabled={!workflowReady} onClick={() => lifecycleAction("start-clinical-review")}><ShieldCheck /> Start review</Button>}
              {draft.status === "in_clinical_review" && can("clinical_rules:clinical_review") && <div className="mt-3 flex flex-wrap items-end gap-2"><label className="type-label">Assign publisher<select className="paper-inset mt-1 block rounded-lg p-1.5 text-xs" value={publisherAssignee} onChange={(event) => setPublisherAssignee(event.target.value)}><option value="">Select publisher</option>{(optionsQuery.data?.publishers || []).map((user) => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select></label><Button size="sm" disabled={!workflowReady || !publisherAssignee} onClick={() => lifecycleAction("clinical-review", { approve: true, reason: draft.change_summary || "Clinical content approved", publisher: publisherAssignee })}><Check /> Approve</Button><Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => lifecycleAction("clinical-review", { approve: false, reason: draft.change_summary || "Clinical changes required" })}>Reject</Button></div>}
              {draft.status === "approved" && can("clinical_rules:publish") && <div className="mt-3 space-y-2"><p className="type-meta text-muted-foreground">Publishing applies to new report generation for {draft.scope.asp_id} / {draft.scope.subpanel_id} ({draft.scope.analyte}, {draft.scope.language}). {draft.scope.subpanel_id === "base" ? "Base also serves subpanels without their own published release." : "This replaces Base selection for this subpanel."} Saved reports remain unchanged.</p><Button size="sm" onClick={() => lifecycleAction("publish")}><FileCheck2 /> Publish</Button></div>}
              {draft.status === "published" && can("clinical_rules:retire") && <Button className="mt-3" size="sm" variant="outline" onClick={retireRuleSet}><Trash2 /> Retire</Button>}
              {validationQuery.data && <div className={cn("mt-3 rounded-lg border p-2 text-xs", validationQuery.data.valid ? "border-success/40 bg-success/10" : "border-destructive/40 bg-destructive/10")}><strong>{validationQuery.data.valid ? "Ready for review" : "Validation requires attention"}</strong>{[...validationQuery.data.errors, ...validationQuery.data.warnings].map((message) => <p key={message} className="mt-1">{message}</p>)}</div>}
            </div>
            <div className={cn("clinical-rules-editor-layout min-h-0", sectionsCollapsed && "is-sections-collapsed")} style={{ "--sections-width": `${sectionsWidth}px` } as CSSProperties}>
              <aside className={cn("min-h-0 border-b border-border bg-muted/15 md:border-b-0", !sectionsCollapsed && "overflow-y-auto p-2")}>
                {sectionsCollapsed ? <div className="clinical-rules-section-rail"><Button type="button" variant="ghost" size="icon-sm" title="Expand report sections" aria-label="Expand report sections" onClick={() => setSectionsCollapsed(false)}><PanelLeftOpen /></Button><nav aria-label="Collapsed report sections">{draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <button key={item.block_id} type="button" title={item.section} aria-label={`Select section ${item.section}`} className={cn("clinical-rules-section-tab", tone.rail, selectedBlock === index && "is-active")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span>{item.section}</span></button> })}</nav></div> : <>
                <div className="mb-2 flex items-center justify-between gap-2"><span className="type-label">Sections</span><Button size="icon-sm" variant="ghost" title="Collapse report sections" aria-label="Collapse report sections" onClick={() => setSectionsCollapsed(true)}><PanelLeftClose /></Button></div>
                {draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <div key={item.block_id} className="mb-1 flex items-center gap-1"><button type="button" className={cn("min-w-0 flex-1 rounded-md border p-2 text-left text-sm", selectedBlock === index ? tone.surface : "border-transparent hover:bg-muted")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span className="block truncate font-medium">{item.section}</span><span className="text-xs text-muted-foreground">{item.rules.length} rules · {item.evaluation.mode.replaceAll("_", " ")}</span></button>{editableDraft && <Button type="button" variant="ghost" size="icon-sm" title="Remove section" onClick={() => mutateDraft((document) => { document.blocks.splice(index, 1); setSelectedBlock(Math.max(0, Math.min(selectedBlock, document.blocks.length - 1))); setSelectedRule(0) })}><Trash2 /></Button>}</div> })}
                {editableDraft && <Button className="mt-2 w-full" variant="outline" size="sm" onClick={() => mutateDraft((document) => document.blocks.push(newRuleBlock(document.blocks)))}><Plus /> Add section</Button>}
                </>}
              </aside>
              {!sectionsCollapsed && <ResizeDivider label="Resize report sections" width={sectionsWidth} setWidth={setSectionsWidth} min={160} max={360} />}
              <div className="min-h-0 min-w-0 overflow-y-auto">
                {block && <div className="space-y-3 border-b border-border p-3">
                  {editableDraft && <div className="grid gap-2 lg:grid-cols-3">
                    <label className="type-label">Output destination<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={["report_header_suffix", "clinical_question"].includes(block.section) ? block.section : "summary"} onChange={(event) => mutateDraft((document) => {
                      const current = document.blocks[selectedBlock]
                      const destination = event.target.value
                      current.section = destination === "summary" ? "Report summary" : destination
                      current.show_heading = destination === "summary"
                      if (destination !== "summary") {
                        current.analysis = null
                        current.evaluation = { mode: "once", collection: null }
                        current.match_strategy = "at_most_one"
                      }
                    })}><option value="summary">Report summary</option><option value="report_header_suffix">Header suffix</option><option value="clinical_question">Clinical question</option></select></label>
                    <label className="type-label">Section<Input className="mt-1" disabled={["report_header_suffix", "clinical_question"].includes(block.section)} value={block.section} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].section = event.target.value; document.blocks[selectedBlock].name = event.target.value })} /></label>
                    <label className="type-label">Section identifier<Input className="mt-1" value={block.block_id} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].block_id = event.target.value })} /></label>
                    <label className="type-label">Analysis<select disabled={metadataOutput} className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.analysis || ""} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].analysis = event.target.value || null })}><option value="">Whole report</option>{Object.keys(draft.analysis_declarations).map((analysis) => <option key={analysis} value={analysis}>{analysis}</option>)}</select></label>
                    <label className="type-label">Evaluate<select disabled={metadataOutput} className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.evaluation.mode} onChange={(event) => mutateDraft((document) => { const mode = event.target.value as RuleBlock["evaluation"]["mode"]; document.blocks[selectedBlock].evaluation = mode === "each_item" ? { mode, collection: "findings" } : { mode, collection: null } })}><option value="once">Once per report</option><option value="each_finding">For each finding</option><option value="each_item">For each collection item</option></select></label>
                    <label className="type-label">Match behavior<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.match_strategy} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].match_strategy = event.target.value as RuleBlock["match_strategy"] })}><option value="first_match" disabled={!!block.conflict_group}>First match</option><option value="all_matches" disabled={!!block.conflict_group}>All matches</option><option value="exactly_one">Exactly one</option><option value="at_most_one">At most one</option></select></label>
                    <label className="type-label">Conflict group (optional)<Input className="mt-1" value={block.conflict_group || ""} onChange={(event) => mutateDraft((document) => {
                      const current = document.blocks[selectedBlock]
                      current.conflict_group = event.target.value || null
                      if (current.conflict_group) {
                        if (!["exactly_one", "at_most_one"].includes(current.match_strategy)) current.match_strategy = "at_most_one"
                      }
                    })} /></label>
                  </div>}
                  {editableDraft && block.evaluation.mode === "each_item" && <label className="type-label block max-w-xs">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.evaluation.collection || "findings"} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].evaluation.collection = event.target.value as NonNullable<RuleBlock["evaluation"]["collection"]> })}><option value="findings">Findings</option><option value="biomarkers">Biomarkers</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>}
                  {editableDraft && <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={metadataOutput} checked={block.show_heading} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].show_heading = event.target.checked })} /> Show section heading</label>}
                  <div className="flex gap-2 overflow-x-auto">{block.rules.map((item, index) => <div key={item.rule_id} className={cn("flex shrink-0 items-center rounded-md", selectedRule === index ? "bg-primary text-primary-foreground" : "bg-muted")}><button type="button" className="px-3 py-1.5 text-sm" onClick={() => setSelectedRule(index)}>{item.name}</button>{editableDraft && block.rules.length > 1 && <Button type="button" variant="ghost" size="icon-sm" title="Remove rule" onClick={() => mutateDraft((document) => { document.blocks[selectedBlock].rules.splice(index, 1); setSelectedRule(Math.max(0, Math.min(selectedRule, document.blocks[selectedBlock].rules.length - 1))) })}><Trash2 /></Button>}</div>)}{editableDraft && <Button className="shrink-0" variant="outline" size="sm" onClick={() => mutateDraft((document) => { const currentBlock = document.blocks[selectedBlock]; const allRuleIds = document.blocks.flatMap((item) => item.rules.map((itemRule) => itemRule.rule_id)); currentBlock.rules.push(newRule(currentBlock, allRuleIds)); setSelectedRule(currentBlock.rules.length - 1) })}><Plus /> Add rule</Button>}</div>
                </div>}
                {rule && block ? <fieldset disabled={!editableDraft}><RuleEditor rule={rule} block={block} facts={facts} controlledValues={controlledValues} change={(next) => mutateDraft((document) => { document.blocks[selectedBlock].rules[selectedRule] = next })} /></fieldset> : <div className="grid min-h-72 place-items-center p-8 text-center"><div><p className="text-sm text-muted-foreground">This rule set does not have an authored section yet.</p>{editableDraft && <Button className="mt-3" variant="outline" onClick={() => mutateDraft((document) => document.blocks.push(newRuleBlock(document.blocks)))}><Plus /> Add first section</Button>}</div></div>}
              </div>
            </div>
          </>}
        </main>
        <ResizeDivider label="Resize text preview" width={previewWidth} setWidth={setPreviewWidth} min={280} max={720} direction={-1} />
        <aside className="min-h-0 min-w-0 overflow-y-auto bg-muted/10 p-4">
          <div className="flex items-center justify-between"><h2 className="type-section-title">Live text preview</h2><GitCompareArrows className="h-4 w-4 text-primary" /></div>
          <div className={cn("mt-3 whitespace-pre-wrap rounded-lg border p-4 text-sm leading-relaxed", clinicalRuleSectionTone(selectedBlock).surface)}>{selectedPreview}</div>
          {editableDraft && <section className="mt-5 border-t border-border pt-4"><h2 className="type-section-title">Report analyses</h2><div className="mt-2 space-y-2">{ANALYSES[draft.scope.analyte].map((analysis) => <label key={analysis} className="flex items-center justify-between gap-3 text-sm"><span>{analysis}</span><select className="paper-inset rounded-lg p-1.5 text-xs" value={draft.analysis_declarations[analysis]?.narrative || "undeclared"} onChange={(event) => mutateDraft((document) => { if (event.target.value === "undeclared") delete document.analysis_declarations[analysis]; else document.analysis_declarations[analysis] = { narrative: event.target.value as "enabled" | "none" } })}><option value="undeclared">Not declared</option><option value="enabled">Generate text</option><option value="none">No narrative</option></select></label>)}</div></section>}
          {editableDraft && <label className="type-label mt-5 block">Change summary<textarea className="paper-inset mt-1 min-h-24 w-full rounded-lg p-2 text-sm" value={draft.change_summary} onChange={(event) => mutateDraft((document) => { document.change_summary = event.target.value })} /></label>}
          {draft && <div className="mt-5 border-t border-border pt-4 text-xs"><p className="font-semibold">Governance</p><dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-muted-foreground"><dt>Draft author</dt><dd>{draft.created_by || "Unknown"}</dd>{draft.review?.clinical_reviewer && <><dt>Clinical reviewer</dt><dd>{draft.review.clinical_reviewer}</dd></>}{draft.review?.publisher && <><dt>Assigned publisher</dt><dd>{draft.review.publisher}</dd></>}</dl>{draft.review?.clinical_decision_reason && <p className="mt-2 text-foreground">{draft.review.clinical_decision_reason}</p>}</div>}
          {draft && <section className="mt-5 border-t border-border pt-4">
            <Button className="w-full justify-between" type="button" variant="outline" onClick={() => setHistoryOpen((current) => !current)}><span className="flex items-center gap-2"><History /> Revision history</span><span className="text-xs">r{draft.revision}</span></Button>
            {historyOpen && <div className="mt-3 space-y-3">
              {revisionsQuery.isLoading ? <AppLoader label="Loading revision history" /> : revisionItems.length === 0 ? <p className="text-xs text-muted-foreground">No immutable baseline has been captured for this version.</p> : <>
                <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Rule-set revisions">{revisionItems.map((item) => <button type="button" key={item.revision} className={cn("shrink-0 rounded-md border px-2 py-1 text-xs", historicalRevision?.revision === item.revision ? "border-primary bg-primary/10 text-primary" : "border-border bg-background")} onClick={() => setSelectedRevision(item.revision)}>r{item.revision}</button>)}</div>
                {historicalRevision && <div className="rounded-lg border border-border bg-background p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2"><ClinicalRuleStatusBadge status={historicalRevision.document.status} /><time dateTime={historicalRevision.occurred_at}>{new Date(historicalRevision.occurred_at).toLocaleString()}</time></div>
                  <p className="mt-2 font-semibold">{historicalRevision.action.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-muted-foreground">{historicalRevision.actor}</p>
                  {historicalRevision.reason && <p className="mt-2">{historicalRevision.reason}</p>}
                  <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 border-t border-border pt-3"><dt>Version</dt><dd>v{historicalRevision.content_version}, revision {historicalRevision.revision}</dd><dt>Hash</dt><dd className="truncate font-mono" title={historicalRevision.revision_hash}>{historicalRevision.revision_hash}</dd><dt>Previous</dt><dd className="truncate font-mono" title={historicalRevision.previous_revision_hash || "First preserved revision"}>{historicalRevision.previous_revision_hash || "First preserved revision"}</dd></dl>
                  <div className="mt-3 space-y-2 border-t border-border pt-3">{historicalRevision.document.blocks.length === 0 ? <p className="text-muted-foreground">No report sections in this revision.</p> : historicalRevision.document.blocks.map((historyBlock) => <div key={historyBlock.block_id}><p className="font-semibold">{historyBlock.section}</p>{historyBlock.rules.map((historyRule) => <div key={historyRule.rule_id} className="mt-1 rounded-md bg-muted/40 p-2"><p className="font-medium">{historyRule.name}</p><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{outputPreview(historyRule.output, facts)}</p><details className="mt-2"><summary className="cursor-pointer text-primary">Condition and exact definition</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-2 font-mono text-xs">{JSON.stringify(historyRule, null, 2)}</pre></details></div>)}</div>)}</div>
                </div>}
              </>}
            </div>}
          </section>}
        </aside>
      </div>
      <ConfirmationDialog open={deleteDraftOpen} title="Delete draft?" description="This permanently removes the editable draft and its draft revision history. Published rule-set versions cannot be deleted." confirmLabel="Delete draft" isPending={deleteDraftMutation.isPending} onConfirm={deleteDraft} onCancel={() => setDeleteDraftOpen(false)} />
    </PageShell>
  )
}
