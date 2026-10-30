import { AppLoader } from "@/components/layout/AppLoader"
import { MarkdownComposer } from "@/components/comments/MarkdownComposer"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { RecordProvenance } from "./RecordProvenance"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Input } from "@/components/ui/input"
import { SearchInput } from "@/components/ui/search-input"
import { FileUpload } from "@/components/ui/file-upload"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { shortResourceName } from "@/lib/resource-names"
import { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { DocumentEditorNotice } from "@/components/admin/DocumentEditorNotice"
import { cn } from "@/lib/utils"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { Link } from "react-router-dom"
import { ANALYSES, clone, emptyRuleSetScope, generatedRuleSetName, newRule, newRuleBlock, orderedRuleSet, ruleSectionLabel, SECTION_STARTERS, sectionStarter, type CreationMode, type NewRuleSetScope } from "./clinical-rule-authoring"
import type {
  ClinicalRuleAssayOption,
  BulkAnnotationGroupOption,
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
import { conditionError } from "./rule-condition-values"
import { outputPreview } from "./rule-output-preview"
import { RuleSetPreview } from "./RuleSetPreview"
import { BulkAnnotationEditor, BulkAnnotationPreview } from "./BulkAnnotationEditor"
import { useRuleWorkspaceLayout } from "@/hooks/useRuleWorkspaceLayout"
import { RuleEditor } from "./RuleEditor"
import { RuleHelp } from "./RuleHelp"
import { ResizeDivider } from "@/components/admin/RuleWorkspaceDivider"

export function ClinicalRulesPage() {
  const queryClient = useQueryClient()
  const access = useCurrentUserAccess()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<ClinicalRuleSet | null>(null)
  const [selectedBlock, setSelectedBlock] = useState(0)
  const [selectedRule, setSelectedRule] = useState(0)
  const [workspaceTab, setWorkspaceTab] = useState<"report" | "annotation">("report")
  const [annotationTier, setAnnotationTier] = useState<1 | 2 | 3>(1)
  const [dirty, setDirty] = useState(false)
  const [textError, setTextError] = useState("")
  const [failedSaveGeneration, setFailedSaveGeneration] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [newScope, setNewScope] = useState<NewRuleSetScope>(emptyRuleSetScope)
  const [newNameEdited, setNewNameEdited] = useState(false)
  const [linkAssay, setLinkAssay] = useState("")
  const [linkDiagnosis, setLinkDiagnosis] = useState("base")
  const [creationMode, setCreationMode] = useState<CreationMode>("blank")
  const [templateId, setTemplateId] = useState("")
  const [importDocument, setImportDocument] = useState<Record<string, unknown> | null>(null)
  const [importError, setImportError] = useState("")
  const [includeExportMetadata, setIncludeExportMetadata] = useState(false)
  const [reviewerAssignee, setReviewerAssignee] = useState("")
  const [publisherAssignee, setPublisherAssignee] = useState("")
  const {
    listCollapsed: ruleListCollapsed, setListCollapsed: setRuleListCollapsed,
    listWidth: ruleListWidth, setListWidth: setRuleListWidth,
    sectionsCollapsed, setSectionsCollapsed, sectionsWidth, setSectionsWidth,
    previewWidth, setPreviewWidth,
  } = useRuleWorkspaceLayout("clinical")
  const [historyOpen, setHistoryOpen] = useState(false)
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null)
  const [deleteDraftOpen, setDeleteDraftOpen] = useState(false)
  const editGeneration = useRef(0)

  const listQuery = useQuery({ queryKey: ["clinical-rule-sets", search, status], queryFn: () => api.get<{ items: ClinicalRuleSet[] }>(`/admin/clinical-rule-sets?q=${encodeURIComponent(search)}${status ? `&status=${status}` : ""}`).then((response) => response.data) })
  const templateQuery = useQuery({ queryKey: ["clinical-rule-templates"], enabled: creating, queryFn: () => api.get<{ items: ClinicalRuleSet[] }>("/admin/clinical-rule-sets?status=published&per_page=200").then((response) => response.data) })
  const factsQuery = useQuery({ queryKey: ["clinical-rule-facts"], queryFn: () => api.get<{ items: FactDefinition[] }>("/admin/clinical-rule-sets/facts").then((response) => response.data) })
  const optionsQuery = useQuery({ queryKey: ["clinical-rule-authoring-options"], queryFn: () => api.get<{ bulk_annotation_fact_paths?: string[]; bulk_annotation_groups?: BulkAnnotationGroupOption[]; assays: ClinicalRuleAssayOption[]; condition_values: Record<string, string[]>; clinical_reviewers: ClinicalRuleReviewerOption[]; publishers: ClinicalRuleReviewerOption[]; sentence_terminology: Record<string, Record<string, unknown>> }>("/admin/clinical-rule-sets/authoring-options").then((response) => response.data) })
  const versionQuery = useQuery({ queryKey: ["clinical-rule-set", selectedId], enabled: Boolean(selectedId), queryFn: () => api.get<ClinicalRuleSet>(`/admin/clinical-rule-sets/versions/${selectedId}`).then((response) => response.data) })
  const revisionsQuery = useQuery({ queryKey: ["clinical-rule-revisions", selectedId], enabled: Boolean(selectedId) && historyOpen, queryFn: () => api.get<{ items: ClinicalRuleRevision[] }>(`/admin/clinical-rule-sets/versions/${selectedId}/revisions`).then((response) => response.data) })
  useEffect(() => {
    if (selectedId && versionQuery.data?._id === selectedId) {
      setDraft(orderedRuleSet(versionQuery.data))
      setDirty(false)
      setSelectedBlock(0)
      setSelectedRule(0)
      setSelectedRevision(null)
    }
  }, [selectedId, versionQuery.data])
  const facts = useMemo(() => factsQuery.data?.items || [], [factsQuery.data?.items])
  const controlledValues = useMemo(() => optionsQuery.data?.condition_values || {}, [optionsQuery.data?.condition_values])
  const annotationGroups = useMemo(() => optionsQuery.data?.bulk_annotation_groups || [], [optionsQuery.data?.bulk_annotation_groups])
  const annotationFacts = useMemo(() => {
    const labels = Object.fromEntries(annotationGroups.map(group => [group.group_id,
      `${[...group.path_names].reverse().join(" › ")} (${group.group_id})${group.is_active ? "" : " · inactive"}`]))
    return facts.filter(fact => optionsQuery.data?.bulk_annotation_fact_paths?.includes(fact.path))
      .map(fact => fact.group === "Biological group" ? { ...fact, value_labels: labels } : fact)
  }, [facts, annotationGroups, optionsQuery.data?.bulk_annotation_fact_paths])
  useEffect(() => { if (draft?.scope.analyte !== "dna") setWorkspaceTab("report") }, [draft?.scope.analyte])
  const conditionProblem = [...(draft?.blocks.flatMap(item => item.rules) || []), ...(draft?.bulk_annotation_rules || [])].map(item => conditionError(item.condition, facts, controlledValues)).find(Boolean) || ""
  const localProblem = textError || conditionProblem
  useEffect(() => { setTextError("") }, [selectedId, selectedBlock, selectedRule])
  useEffect(() => { setLinkAssay(""); setLinkDiagnosis("base") }, [selectedId])

  const documentEditor = useDocumentEditor("clinical-rules", draft?._id || "", Boolean(draft?.status === "draft" && !draft.system_installed && hasPermission(access.data, "clinical_rules:draft")))
  const saveMutation = useMutation({
    retry: false,
    mutationFn: ({ document, generation, scope }: { document: ClinicalRuleSet; generation: number; scope?: ClinicalRuleSet["scope"] }) => api.patch<ClinicalRuleSet>(`/admin/clinical-rule-sets/drafts/${document._id}`, { revision: document.revision, ...(scope ? { scope } : {}), name: document.name, analysis_declarations: document.analysis_declarations, terminology: document.terminology, blocks: document.blocks, bulk_annotation_rules: document.bulk_annotation_rules || [], test_cases: document.test_cases, references: document.references, change_summary: document.change_summary }, documentEditor.options()).then((response) => ({ document: response.data, generation })),
    onSuccess: ({ document, generation }) => { setDraft((current) => generation === editGeneration.current ? orderedRuleSet(document) : current ? { ...current, revision: document.revision } : current); if (generation === editGeneration.current) setDirty(false); queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] }); queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] }) },
    onError: (_error, variables) => setFailedSaveGeneration(variables.generation),
  })
  const saveDraft = saveMutation.mutate
  const savePending = saveMutation.isPending
  useEffect(() => {
    if (!dirty || draft?.status !== "draft" || savePending || !documentEditor.owned || localProblem || failedSaveGeneration === editGeneration.current) return
    const generation = editGeneration.current
    const timer = window.setTimeout(() => saveDraft({ document: draft, generation }), 800)
    return () => window.clearTimeout(timer)
  }, [dirty, draft, saveDraft, savePending, documentEditor.owned, localProblem, failedSaveGeneration])

  const mutateDraft = (change: (document: ClinicalRuleSet) => void) => {
    if (!hasPermission(access.data, "clinical_rules:draft") || !documentEditor.owned) return
    setDraft((current) => { if (!current || current.status !== "draft") return current; const next = clone(current); change(next); return next })
    editGeneration.current += 1
    setDirty(true)
  }
  const block = draft?.blocks[selectedBlock]
  const metadataOutput = !!block && ["report_header_suffix", "clinical_question"].includes(block.section)
  const rule = block?.rules[selectedRule]
  const can = (permission: string) => hasPermission(access.data, permission)
  const currentUsername = access.data?.username?.trim().toLowerCase()
  const canReviewVersion = !!currentUsername && !!draft &&
    can("clinical_rules:clinical_review") &&
    draft.review?.clinical_reviewer?.trim().toLowerCase() === currentUsername &&
    draft.updated_by.trim().toLowerCase() !== currentUsername &&
    draft.review?.submitted_by?.trim().toLowerCase() !== currentUsername
  const editableDraft = documentEditor.owned && draft?.status === "draft" && !draft.system_installed && can("clinical_rules:draft")
  const deletableVersion = draft && !draft.system_installed && ["draft", "submitted", "in_clinical_review", "approved", "rejected"].includes(draft.status) && can("clinical_rules:draft")
  const workflowReady = !dirty && !saveMutation.isPending && !localProblem

  const beginCreation = (mode: CreationMode = "blank") => {
    setSelectedId(null)
    setDraft(null)
    setSelectedBlock(0)
    setSelectedRule(0)
    setNewScope(emptyRuleSetScope())
    setNewNameEdited(false)
    setCreationMode(mode)
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

  const actionMutation = useMutation({ mutationFn: ({ path, body = {} }: { path: string; body?: Record<string, unknown> }) => api.post<ClinicalRuleSet>(path, body, documentEditor.options()).then((response) => response.data), onSuccess: (document) => {
    setSelectedId(document._id); setDraft(orderedRuleSet(document)); setDirty(false); setCreating(false)
    void queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] })
    void queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] })
    if (document.status === "published" || document.status === "retired") {
      void queryClient.invalidateQueries({ queryKey: ["report-preview"] })
      void queryClient.invalidateQueries({ queryKey: ["admin-resource-context", "aspc"] })
      void queryClient.invalidateQueries({ queryKey: ["assay-setup-context"] })
    }
  } })
  const deleteDraftMutation = useMutation({
    mutationFn: ({ documentId, revision }: { documentId: string; revision: number }) => api.delete(`/admin/clinical-rule-sets/drafts/${documentId}?revision=${revision}`, documentEditor.options()),
    onSuccess: (_, { documentId }) => {
      setDeleteDraftOpen(false)
      setSelectedId(null)
      setDraft(null)
      setDirty(false)
      setHistoryOpen(false)
      queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] })
      queryClient.removeQueries({ queryKey: ["clinical-rule-set", documentId], type: "inactive" })
      queryClient.removeQueries({ queryKey: ["clinical-rule-revisions", documentId], type: "inactive" })
    },
  })
  const createRevision = () => draft && actionMutation.mutate({ path: "/admin/clinical-rule-sets/drafts", body: { source_version_id: draft._id, source: "template" } })
  const createRuleSet = () => {
    const scope = { asp_id: newScope.asp_id.trim(), diagnosis_id: newScope.diagnosis_id.trim(), analyte: newScope.analyte, language: newScope.language.trim() }
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
  const revisionItems = revisionsQuery.data?.items || []
  const historicalRevision = revisionItems.find((item) => item.revision === selectedRevision) || revisionItems[0]
  const assayTemplates = (templateQuery.data?.items || []).filter((item) => item.scope.asp_id === newScope.asp_id)
  const downloadRuleSet = async () => {
    if (!draft) return
    const exportDocument = await api.get<Record<string, unknown>>(`/admin/clinical-rule-sets/versions/${draft._id}/export${includeExportMetadata ? "?include_metadata=true" : ""}`).then((response) => response.data)
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
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Expected a rule-set object")
        setImportDocument(parsed)
        setImportError("")
        const scope = parsed.scope as Record<string, unknown> | undefined
        if (scope && typeof scope.asp_id === "string" && typeof scope.diagnosis_id === "string" && typeof scope.language === "string" && ["dna", "rna"].includes(String(scope.analyte))) {
          setNewScope({ asp_id: scope.asp_id, diagnosis_id: scope.diagnosis_id, language: scope.language, analyte: scope.analyte as "dna" | "rna", name: typeof parsed.name === "string" ? parsed.name : "Imported report rules" })
        }
      } catch {
        setImportDocument(null)
        setImportError("Choose a valid clinical-rule JSON export.")
      }
    }
    reader.readAsText(file)
  }

  if (listQuery.isLoading || factsQuery.isLoading || optionsQuery.isLoading) return <PageShell eyebrow="Clinical reporting" title="Reporting Rule Sets"><AppLoader label="Loading clinical rules" /></PageShell>
  return (
    <PageShell eyebrow="Clinical reporting" title="Reporting Rule Sets" description="Author, review, validate, and publish governed report wording." actions={<>{dirty || saveMutation.isPending ? <Badge variant="outline"><icon.save /> {saveMutation.isPending ? "Saving" : "Unsaved"}</Badge> : draft?.status === "draft" ? <Badge variant="outline"><icon.check /> Saved</Badge> : null}{can("clinical_rules:test") && <Button variant="outline" nativeButton={false} render={<Link to="/admin/clinical-rules/testing" />}><icon.beaker /> Test rules</Button>}{can("clinical_rules:draft") && !creating && <Button variant="outline" disabled={!workflowReady} onClick={() => beginCreation()}><icon.plus /> New rule set</Button>}{draft?.status !== "draft" && draft && can("clinical_rules:draft") && <Button onClick={createRevision}><icon.copyPlus /> Create revision</Button>}</>}>
      <DocumentEditorNotice editor={documentEditor} />
      {localProblem && <p role="alert" className="mb-3 rounded-lg border border-warning p-3 type-body">Correct the current edit before saving: {localProblem}</p>}
      {saveMutation.isError && failedSaveGeneration === editGeneration.current && <div role="alert" className="mb-3 rounded-lg border border-destructive p-3 type-body"><p>Autosave paused. {saveMutation.error instanceof Error ? saveMutation.error.message : "The draft could not be saved."} Correct the draft or retry when ready.</p><Button variant="outline" size="sm" disabled={!!localProblem} onClick={() => { saveMutation.reset(); setFailedSaveGeneration(null) }}>Retry save</Button></div>}
      {creating && (
        <section className="surface-panel mb-3 p-4" aria-label="Create clinical rule set">
          <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Draft creation method">
            {(["blank", "template", "import"] as CreationMode[]).map((mode) => <Button key={mode} type="button" size="sm" variant={creationMode === mode ? "default" : "outline"} onClick={() => setCreationMode(mode)}>{mode === "blank" ? "Build in UI" : mode === "template" ? "Use template" : "Import JSON"}</Button>)}
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <label className="type-label">Assay<Input aria-label="Assay" list="clinical-rule-assays" className="mt-1" placeholder="Choose or enter planned assay ID" value={newScope.asp_id} onChange={(event) => { const assay = optionsQuery.data?.assays.find((item) => item.asp_id === event.target.value); setNewScope((current) => ({ ...current, asp_id: event.target.value, analyte: assay?.analyte || current.analyte, diagnosis_id: "base", name: newNameEdited ? current.name : generatedRuleSetName(assay, "base") })) }} /><datalist id="clinical-rule-assays">{(optionsQuery.data?.assays || []).map((assay) => <option key={assay.asp_id} value={assay.asp_id}>{shortResourceName(assay, assay.asp_id)}</option>)}</datalist></label>
            <label className="type-label">Diagnosis<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={newScope.diagnosis_id} onChange={(event) => { const diagnosisId = event.target.value; const assay = optionsQuery.data?.assays.find((item) => item.asp_id === newScope.asp_id); setNewScope((current) => ({ ...current, diagnosis_id: diagnosisId, name: newNameEdited ? current.name : generatedRuleSetName(assay, diagnosisId) })) }}><option value="base">Base (base)</option>{(optionsQuery.data?.assays.find((item) => item.asp_id === newScope.asp_id)?.diagnoses || []).filter(scope => scope.diagnosis_id !== "base").map((scope) => <option key={scope.diagnosis_id} value={scope.diagnosis_id}>{scope.display_name} ({scope.diagnosis_id})</option>)}{newScope.diagnosis_id !== "base" && !optionsQuery.data?.assays.find(item => item.asp_id === newScope.asp_id)?.diagnoses?.some(item => item.diagnosis_id === newScope.diagnosis_id) && <option value={newScope.diagnosis_id}>{newScope.diagnosis_id} (planned)</option>}</select></label>
            <label className="type-label">Analyte<select className="paper-inset mt-1 w-full rounded-lg p-2 type-body" disabled={!!optionsQuery.data?.assays.some(item => item.asp_id === newScope.asp_id)} value={newScope.analyte} onChange={event => setNewScope({ ...newScope, analyte: event.target.value as "dna" | "rna" })}><option value="dna">DNA</option><option value="rna">RNA</option></select></label>
            <label className="type-label">Language<Input className="mt-1" value={newScope.language} onChange={(event) => setNewScope({ ...newScope, language: event.target.value })} /></label>
            <label className="type-label">Rule-set name<Input className="mt-1" value={newScope.name} onChange={(event) => { setNewNameEdited(true); setNewScope({ ...newScope, name: event.target.value }) }} /></label>
          </div>
          {newScope.asp_id && !optionsQuery.data?.assays.some(item => item.asp_id === newScope.asp_id) && <p className="mt-2 type-body-sm text-muted-foreground">This assay is not registered yet. You can author this draft now, then register the assay or link the draft to an available assay before submitting it for review.</p>}
          {creationMode === "template" && <label className="type-label mt-3 block max-w-xl">Template rule set<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={templateId} onChange={(event) => { const selected = assayTemplates.find((item) => item._id === event.target.value); setTemplateId(event.target.value); if (selected && !newNameEdited) setNewScope((current) => ({ ...current, name: `${selected.name} - test` })) }}><option value="">Select a published {newScope.asp_id ? "assay-specific" : ""} template</option>{assayTemplates.map((item) => <option key={item._id} value={item._id}>{item.scope.diagnosis_id} · {item.name} (v{item.content_version})</option>)}</select></label>}
          {creationMode === "import" && <div className="mt-3 max-w-xl"><p className="type-label mb-2">Rule configuration JSON</p><FileUpload label="Rule configuration JSON" hint="Upload rule configuration (.json). Author, timestamps and version are assigned automatically." accept="application/json,.json" onChange={(event) => chooseImport(event.target.files?.[0])} />{importDocument && <p className="mt-1 type-meta text-pass">Valid JSON loaded. It will be validated again by the server before a draft is created.</p>}{importError && <p role="alert" className="mt-1 type-meta text-destructive">{importError}</p>}</div>}
          <div className="mt-3 flex justify-end gap-2"><Button variant="ghost" onClick={cancelCreation}>Cancel</Button><Button disabled={!newScope.asp_id.trim() || !newScope.diagnosis_id.trim() || !newScope.name.trim() || actionMutation.isPending || (creationMode === "template" && !templateId) || (creationMode === "import" && !importDocument)} onClick={createRuleSet}><icon.circlePlus /> Create draft</Button></div>
        </section>
      )}
      <div className={cn("clinical-rules-layout clinical-rules-workspace surface-panel overflow-hidden", ruleListCollapsed && "is-rule-list-collapsed")} style={{ "--rule-list-width": `${ruleListWidth}px`, "--preview-width": `${previewWidth}px` } as CSSProperties}>
        <aside className="flex min-h-0 min-w-0 flex-col border-b border-border xl:border-b-0">
          {ruleListCollapsed ? <button type="button" className="clinical-rules-rail" aria-label="Expand rule-set list" onClick={() => setRuleListCollapsed(false)}><icon.panelLeftOpen /><span>Rule sets</span></button> : <>
          <div className="space-y-2 border-b border-border p-3">
            <div className="flex items-center gap-1"><SearchInput aria-label="Search clinical rules" placeholder="Search rules" value={search} onChange={(event) => setSearch(event.target.value)} /><Button size="icon-sm" variant="ghost" title="Collapse rule-set list" aria-label="Collapse rule-set list" onClick={() => setRuleListCollapsed(true)}><icon.panelLeftClose /></Button></div>
            <select className="paper-inset w-full rounded-lg p-2 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All workflow states</option>{Object.entries(CLINICAL_RULE_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          </div>
          <nav className="min-h-0 flex-1 overflow-y-auto p-2" aria-label="Clinical rule sets">
            {(listQuery.data?.items || []).map((item) => <button type="button" key={item._id} disabled={!workflowReady} className={cn("mb-1 w-full rounded-lg p-3 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60", selectedId === item._id && "bg-primary/10 ring-1 ring-primary/30")} onClick={() => openRuleSet(item._id)}><span className="block truncate text-sm font-semibold">{item.name}</span><span className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{item.scope.asp_id} · {item.scope.diagnosis_id}</span><ClinicalRuleStatusBadge status={item.status} prefix={`v${item.content_version} `} /></span></button>)}
          </nav>
          </>}
        </aside>
        {!ruleListCollapsed && <ResizeDivider label="Resize rule-set list" width={ruleListWidth} setWidth={setRuleListWidth} min={210} max={440} />}
        <main className="grid min-h-0 min-w-0 grid-rows-[auto_auto_auto_minmax(0,1fr)] border-b border-border xl:border-b-0 xl:border-r">
          {!draft ? <div className="grid h-full place-items-center p-8 text-sm text-muted-foreground">Select a rule set to inspect or edit.</div> : <>
            <div className="border-b border-border bg-muted/35 p-3">
              {editableDraft && <details className="mb-3 rounded-lg border border-border bg-background p-3">
                <summary className="cursor-pointer type-body-sm font-medium">Assay association: {draft.scope.asp_id} · {draft.scope.diagnosis_id}{!optionsQuery.data?.assays.some(item => item.asp_id === draft.scope.asp_id) ? " (not registered yet)" : ""}</summary>
                <p className="my-2 type-body-sm text-muted-foreground">Keep authoring while the assay is being prepared. Register the planned assay ID or link this draft to an available assay below before review. Linking preserves this document and its revision history. Review any conditions containing assay IDs after changing the scope.</p>
                <div className="flex flex-wrap items-end gap-2">
                  <label className="type-label">Link to assay<select aria-label="Link to assay" className="paper-inset mt-1 block rounded-lg p-2 type-body" value={linkAssay} onChange={event => { setLinkAssay(event.target.value); setLinkDiagnosis("base") }}><option value="">Select assay</option>{(optionsQuery.data?.assays || []).filter(item => item.analyte === draft.scope.analyte).map(item => <option key={item.asp_id} value={item.asp_id} title={item.display_name}>{shortResourceName(item, item.asp_id)}</option>)}</select></label>
                  <label className="type-label">Link to diagnosis<select aria-label="Link to diagnosis" className="paper-inset mt-1 block rounded-lg p-2 type-body" value={linkDiagnosis} onChange={event => setLinkDiagnosis(event.target.value)}><option value="base">Base</option>{(optionsQuery.data?.assays.find(item => item.asp_id === linkAssay)?.diagnoses || []).filter(item => item.diagnosis_id !== "base").map(item => <option key={item.diagnosis_id} value={item.diagnosis_id}>{item.display_name}</option>)}</select></label>
                  <Button variant="outline" size="sm" disabled={!workflowReady || !linkAssay} onClick={() => saveDraft({ document: draft, generation: editGeneration.current, scope: { ...draft.scope, asp_id: linkAssay, diagnosis_id: linkDiagnosis } })}>Link assay</Button>
                </div>
              </details>}
              <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">{editableDraft ? <Input aria-label="Rule-set name" className="max-w-xl font-semibold" value={draft.name} onChange={(event) => mutateDraft((document) => { document.name = event.target.value })} /> : <h2 className="font-semibold">{draft.name}</h2>}<p className="mt-1 text-xs text-muted-foreground">{draft.rule_set_id} · version {draft.content_version} · revision {draft.revision}</p></div><div className="flex flex-wrap items-center gap-2">{!editableDraft && <Badge variant="outline">Read-only</Badge>}{can("clinical_rules:draft") && <Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => beginCreation("import")}><icon.upload /> Import JSON</Button>}<label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={includeExportMetadata} onChange={event => setIncludeExportMetadata(event.target.checked)} />Include metadata</label><Button size="sm" variant="outline" onClick={downloadRuleSet}><icon.download /> Export JSON</Button><ClinicalRuleStatusBadge status={draft.status} /></div></div>
              {editableDraft && <div className="mt-3 flex flex-wrap items-end gap-2"><Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => validationQuery.refetch()}><icon.fileCheck2 /> Validate</Button>{can("clinical_rules:submit") && <label className="type-label">Assign clinical reviewer<select className="paper-inset mt-1 block rounded-lg p-1.5 text-xs" value={reviewerAssignee} onChange={(event) => setReviewerAssignee(event.target.value)}><option value="">Select reviewer</option>{(optionsQuery.data?.clinical_reviewers || []).filter(user => user.username.trim().toLowerCase() !== access.data?.username?.trim().toLowerCase()).map((user) => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select></label>}{can("clinical_rules:submit") && <Button size="sm" disabled={!workflowReady || !reviewerAssignee} onClick={() => lifecycleAction("submit", { reason: draft.change_summary || "Submitted for clinical review", assignee: reviewerAssignee })}><icon.send /> Submit</Button>}<Button size="sm" variant="destructive" disabled={!workflowReady || deleteDraftMutation.isPending} onClick={() => setDeleteDraftOpen(true)}><icon.trash2 /> Delete draft</Button></div>}
              {draft.status === "submitted" && !draft.system_installed && canReviewVersion && <Button className="mt-3" size="sm" disabled={!workflowReady || actionMutation.isPending} onClick={() => lifecycleAction("start-clinical-review")}><icon.shieldCheck /> Start review</Button>}
              {["submitted", "in_clinical_review", "approved"].includes(draft.status) && !draft.system_installed && can("clinical_rules:draft") && <div className="mt-3 space-y-2"><Button type="button" size="sm" variant="outline" disabled={!workflowReady || actionMutation.isPending} onClick={() => lifecycleAction("reopen", { revision: draft.revision, reason: draft.status === "approved" ? "Reopened for editing; previous approval cleared" : "Review recalled for editing" })}>{draft.status === "approved" ? "Edit again" : "Recall and edit"}</Button><p className="type-meta text-muted-foreground">Return this version to draft and withdraw the current review or approval. Submit it for a fresh review after editing.</p></div>}
              {draft.status === "in_clinical_review" && !draft.system_installed && canReviewVersion && <div className="mt-3 flex flex-wrap items-end gap-2"><label className="type-label">Assign publisher<select className="paper-inset mt-1 block rounded-lg p-1.5 text-xs" value={publisherAssignee} onChange={(event) => setPublisherAssignee(event.target.value)}><option value="">Select publisher</option>{(optionsQuery.data?.publishers || []).map((user) => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select></label><Button size="sm" disabled={!workflowReady || !publisherAssignee} onClick={() => lifecycleAction("clinical-review", { approve: true, reason: draft.change_summary || "Clinical content approved", publisher: publisherAssignee })}><icon.check /> Approve</Button><Button size="sm" variant="outline" disabled={!workflowReady || actionMutation.isPending} onClick={() => lifecycleAction("clinical-review", { approve: false, reason: draft.change_summary || "Clinical changes required" })}>Reject</Button></div>}
              {draft.status === "approved" && !draft.system_installed && can("clinical_rules:publish") && <div className="mt-3 space-y-2"><p className="type-meta text-muted-foreground">Publishing applies to new report generation for {draft.scope.asp_id} / {draft.scope.diagnosis_id} ({draft.scope.analyte}, {draft.scope.language}). {draft.scope.diagnosis_id === "base" ? "Base serves diagnoses without their own release and supplies analysis descriptions to diagnoses that do not define one." : "This replaces Base summary selection for this diagnosis. Analysis descriptions inherit Base unless explicitly defined."} Saved reports remain unchanged.</p><Button size="sm" disabled={!workflowReady || actionMutation.isPending} onClick={() => lifecycleAction("publish")}><icon.fileCheck2 /> Publish</Button></div>}
              {draft.status === "published" && !draft.system_installed && can("clinical_rules:retire") && <Button className="mt-3" size="sm" variant="outline" onClick={retireRuleSet}><icon.trash2 /> Retire</Button>}
              {validationQuery.data && <section role="status" aria-label="Rule validation result" className={cn("mt-3 space-y-2 rounded-lg border p-3 type-body-sm", !validationQuery.data.valid ? "border-destructive/40 bg-destructive/10" : validationQuery.data.warnings.length ? "border-warn/40 bg-warn/10" : "border-success/40 bg-success/10")}>
                <strong>{!validationQuery.data.valid ? "Validation errors" : validationQuery.data.warnings.length ? "Valid for review with warnings" : "Ready for review"}</strong>
                {validationQuery.data.errors.length > 0 && <div><p className="type-label">Errors</p><ul className="list-disc space-y-1 pl-4">{validationQuery.data.errors.map(message => <li key={message}>{message}</li>)}</ul></div>}
                {validationQuery.data.warnings.length > 0 && <div><p className="type-label">Warnings — review these before continuing</p><ul className="list-disc space-y-1 pl-4">{validationQuery.data.warnings.map(message => <li key={message}>{message}</li>)}</ul></div>}
              </section>}
            </div>
            <details className="max-h-80 overflow-y-auto border-b border-border p-3"><summary className="cursor-pointer type-label">Version notes</summary>
              <p className="my-2 type-meta text-muted-foreground">Explain the changes for reviewers and revision history. These notes are not report or annotation text.</p>
              <MarkdownComposer label="Change summary" compact readOnly={!editableDraft} maxLength={null} value={draft.change_summary} onChange={value => mutateDraft(document => { document.change_summary = value })} />
          {draft && <div className="mt-5 border-t border-border pt-4 text-xs"><p className="font-semibold">Governance</p><dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-muted-foreground"><dt>Created by</dt><dd><RecordProvenance record={draft} /></dd><dt>Updated by</dt><dd>{draft.updated_by}</dd>{draft.review?.clinical_reviewer && <><dt>Clinical reviewer</dt><dd>{draft.review.clinical_reviewer}</dd></>}{draft.review?.publisher && <><dt>Assigned publisher</dt><dd>{draft.review.publisher}</dd></>}</dl>{draft.review?.clinical_decision_reason && <MarkdownText className="mt-2 text-foreground" text={draft.review.clinical_decision_reason} />}</div>}
          {draft && <section className="mt-5 border-t border-border pt-4">
            <Button className="w-full justify-between" type="button" variant="outline" onClick={() => setHistoryOpen((current) => !current)}><span className="flex items-center gap-2"><icon.history /> Revision history</span><span className="text-xs">r{draft.revision}</span></Button>
            {historyOpen && <div className="mt-3 space-y-3">
              {revisionsQuery.isLoading ? <AppLoader label="Loading revision history" /> : revisionItems.length === 0 ? <p className="text-xs text-muted-foreground">No immutable baseline has been captured for this version.</p> : <>
                <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Rule-set revisions">{revisionItems.map((item) => <button type="button" key={item.revision} className={cn("shrink-0 rounded-md border px-2 py-1 text-xs", historicalRevision?.revision === item.revision ? "border-primary bg-primary/10 text-primary" : "border-border bg-background")} onClick={() => setSelectedRevision(item.revision)}>r{item.revision}</button>)}</div>
                {historicalRevision && <div className="rounded-lg border border-border bg-background p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2"><ClinicalRuleStatusBadge status={historicalRevision.document.status} /><time dateTime={historicalRevision.occurred_at}>{new Date(historicalRevision.occurred_at).toLocaleString()}</time></div>
                  <p className="mt-2 font-semibold">{historicalRevision.action.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-muted-foreground">{historicalRevision.actor}</p>
                  {historicalRevision.reason && <MarkdownText className="mt-2" text={historicalRevision.reason} />}
                  <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 border-t border-border pt-3"><dt>Version</dt><dd>v{historicalRevision.content_version}, revision {historicalRevision.revision}</dd><dt>Hash</dt><dd className="truncate font-mono" title={historicalRevision.revision_hash}>{historicalRevision.revision_hash}</dd><dt>Previous</dt><dd className="truncate font-mono" title={historicalRevision.previous_revision_hash || "First preserved revision"}>{historicalRevision.previous_revision_hash || "First preserved revision"}</dd></dl>
                  <div className="mt-3 space-y-2 border-t border-border pt-3">{historicalRevision.document.blocks.length === 0 ? <p className="text-muted-foreground">No report sections in this revision.</p> : historicalRevision.document.blocks.map((historyBlock) => <div key={historyBlock.block_id}><p className="font-semibold">{historyBlock.section}</p>{historyBlock.rules.map((historyRule) => <div key={historyRule.rule_id} className="mt-1 rounded-md bg-muted/40 p-2"><p className="font-medium">{historyRule.name}</p><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{outputPreview(historyRule.output, facts)}</p><details className="mt-2"><summary className="cursor-pointer text-primary">Condition and exact definition</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-2 font-mono text-xs">{JSON.stringify(historyRule, null, 2)}</pre></details></div>)}</div>)}</div>
                </div>}
              </>}
            </div>}
          </section>}
            </details>
            <div role="tablist" aria-label="Rule content" className="flex flex-wrap gap-2 border-b border-border p-3">
              {([['report', 'Report wording'], ['annotation', 'Bulk annotation text']] as const).filter(([value]) => value === "report" || draft.scope.analyte === "dna").map(([value, label]) => <Button key={value} id={`rule-tab-${value}`} type="button" role="tab" tabIndex={workspaceTab === value ? 0 : -1} onKeyDown={event => { if (draft.scope.analyte === "dna" && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); const nextTab = event.key === "Home" ? "report" : event.key === "End" ? "annotation" : workspaceTab === "report" ? "annotation" : "report"; setWorkspaceTab(nextTab); document.getElementById(`rule-tab-${nextTab}`)?.focus() } }} aria-selected={workspaceTab === value} aria-controls={`rule-panel-${value}`} variant={workspaceTab === value ? "secondary" : "ghost"} onClick={() => { setWorkspaceTab(value) }}>{label}</Button>)}
            </div>
            <div role="tabpanel" id="rule-panel-annotation" aria-labelledby="rule-tab-annotation" className="min-h-0 overflow-y-auto" hidden={workspaceTab !== "annotation"} style={{ "--sections-width": `${sectionsWidth}px` } as CSSProperties}>
              <BulkAnnotationEditor key={draft._id} sectionsWidth={sectionsWidth} setSectionsWidth={setSectionsWidth} rules={draft.bulk_annotation_rules || []} facts={annotationFacts} controlledValues={controlledValues} editable={Boolean(editableDraft)} tier={annotationTier} setTier={setAnnotationTier} ruleIds={[...draft.blocks.flatMap(item => item.rules.map(rule => rule.rule_id)), ...(draft.bulk_annotation_rules || []).map(rule => rule.rule_id)]} onTextError={setTextError} onChange={rules => mutateDraft(document => { document.bulk_annotation_rules = rules })} />
            </div>
            <div role="tabpanel" id="rule-panel-report" aria-labelledby="rule-tab-report" className="min-h-0 overflow-y-auto" hidden={workspaceTab !== "report"}>
            <div className={cn("clinical-rules-editor-layout min-h-0", sectionsCollapsed && "is-sections-collapsed")} style={{ "--sections-width": `${sectionsWidth}px` } as CSSProperties}>
              <aside className={cn("min-h-0 border-b border-border bg-muted/15 md:border-b-0", !sectionsCollapsed && "overflow-y-auto p-2")}>
                {sectionsCollapsed ? <div className="clinical-rules-section-rail"><Button type="button" variant="ghost" size="icon-sm" title="Expand report sections" aria-label="Expand report sections" onClick={() => setSectionsCollapsed(false)}><icon.panelLeftOpen /></Button><nav aria-label="Collapsed report sections">{draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <button key={item.block_id} type="button" title={ruleSectionLabel(item.section)} aria-label={`Select section ${ruleSectionLabel(item.section)}`} className={cn("clinical-rules-section-tab", tone.rail, selectedBlock === index && "is-active")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span>{ruleSectionLabel(item.section)}</span></button> })}</nav></div> : <>
                <div className="mb-2 flex items-center justify-between gap-2"><span className="type-label">Sections</span><Button size="icon-sm" variant="ghost" title="Collapse report sections" aria-label="Collapse report sections" onClick={() => setSectionsCollapsed(true)}><icon.panelLeftClose /></Button></div>
                {draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <div key={item.block_id} className="mb-1 flex items-center gap-1"><button type="button" className={cn("min-w-0 flex-1 rounded-md border p-2 text-left text-sm", selectedBlock === index ? tone.surface : "border-transparent hover:bg-muted")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span className="block truncate font-medium">{ruleSectionLabel(item.section)}</span><span className="text-xs text-muted-foreground">{item.rules.length} rules · {item.evaluation.mode.replaceAll("_", " ")}</span></button>{editableDraft && <Button type="button" variant="ghost" size="icon-sm" title="Remove section" onClick={() => mutateDraft((document) => { document.blocks.splice(index, 1); setSelectedBlock(Math.max(0, Math.min(selectedBlock - (index < selectedBlock ? 1 : 0), document.blocks.length - 1))); if (index === selectedBlock) setSelectedRule(0) })}><icon.trash2 /></Button>}</div> })}
                {editableDraft && <><label className="type-label mt-3 block">Start a section<select aria-label="Section starter" className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value="" onChange={event => {
                  const key = event.target.value
                  if (!key) return
                  mutateDraft(document => {
                    const starter = sectionStarter(document.blocks, key, { ...document.scope, name: document.name })
                    if (key === "snv_summary" && !document.terminology.tier_summary) {
                      const terms = optionsQuery.data?.sentence_terminology?.[document.scope.language]?.tier_summary
                      if (terms) document.terminology.tier_summary = clone(terms)
                    }
                    document.blocks.push(starter)
                    if (starter.analysis) document.analysis_declarations[starter.analysis] = { narrative: "enabled" }
                    setSelectedBlock(document.blocks.length - 1); setSelectedRule(0)
                  })
                }}><option value="">Choose a section…</option>{SECTION_STARTERS.filter(([, , analysis]) => !analysis || (ANALYSES[draft.scope.analyte] as readonly string[]).includes(analysis)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><p className="mt-2 text-xs text-muted-foreground">Starters add editable rules, initially disabled. Review wording and enable each rule. Introduction and closing text have no heading by default.</p><Button className="clinical-rule-action mt-2 w-full" data-action="section" variant="outline" size="sm" onClick={() => mutateDraft((document) => document.blocks.push(newRuleBlock(document.blocks)))}><icon.plus /> Add section</Button></>}
                </>}
              </aside>
              {!sectionsCollapsed && <ResizeDivider label="Resize report sections" width={sectionsWidth} setWidth={setSectionsWidth} min={160} max={360} />}
              <div className="min-h-0 min-w-0 overflow-y-auto">
                {block && <div className="space-y-3 border-b border-border p-3">
                  {editableDraft && <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-muted-foreground">Section {selectedBlock + 1} of {draft.blocks.length}</span>{([-1, 1] as const).map(direction => <Button key={direction} type="button" variant="outline" size="sm" disabled={selectedBlock + direction < 0 || selectedBlock + direction >= draft.blocks.length} onClick={() => mutateDraft(document => {
                    const destination = selectedBlock + direction
                    const [moved] = document.blocks.splice(selectedBlock, 1)
                    document.blocks.splice(destination, 0, moved)
                    document.blocks.forEach((item, index) => { item.section_order = (index + 1) * 100; item.block_order = (index + 1) * 10 })
                    setSelectedBlock(destination)
                  })}>Move section {direction === -1 ? "up" : "down"}</Button>)}</div>}
                  {editableDraft && <div className="space-y-2">
                    <label className="type-label">Section<Input className="mt-1" disabled={["report_header_suffix", "clinical_question", "analysis_description"].includes(block.section)} value={ruleSectionLabel(block.section)} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].section = event.target.value; document.blocks[selectedBlock].name = event.target.value })} /></label>
                    <div className="flex items-center gap-2"><p className="type-body-sm text-muted-foreground">{block.analysis || "Whole report"} · {block.evaluation.mode === "once" ? "Write once per report" : block.evaluation.mode === "each_finding" ? "Write for each matching finding" : "Write for each matching collection item"}. Choose when the sentence applies, write it, then preview and enable it.</p><RuleHelp label="Build a section">A section groups related sentences. Use the SNV summary starter for positive and negative results, or General introduction for independent method and control sentences. Each starter stays disabled until you review and enable its rules.</RuleHelp></div>
                  </div>}
                  {editableDraft && <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer type-body-sm font-medium">Section settings</summary><div className="my-2 flex items-center gap-2"><p className="type-body-sm text-muted-foreground">Change evaluation and matching only when the starter does not fit your intended wording.</p><RuleHelp label="Evaluation and matching">Once per report is for introductions and aggregate positive/negative summaries. For each finding writes repeated variant sentences. All matches combines independent additions; Exactly one requires one alternative; At most one allows no match; First match uses rule order. Identifiers and conflict groups are advanced controls.</RuleHelp></div><div className="grid gap-2 lg:grid-cols-3">
                    <label className="type-label">Output destination<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={["report_header_suffix", "clinical_question", "analysis_description"].includes(block.section) ? block.section : "summary"} onChange={(event) => mutateDraft((document) => {
                      const current = document.blocks[selectedBlock]
                      const destination = event.target.value
                      current.section = destination === "summary" ? "Report summary" : destination
                      current.show_heading = destination === "summary"
                      if (destination === "analysis_description") {
                        current.match_strategy = "all_matches"
                      } else if (destination !== "summary") {
                        current.analysis = null
                        current.evaluation = { mode: "once", collection: null }
                        current.match_strategy = "at_most_one"
                        current.rules.forEach(item => { item.presentation = "paragraph" })
                      }
                    })}><option value="summary">Report summary</option><option value="analysis_description">Analysis description</option><option value="report_header_suffix">Header suffix</option><option value="clinical_question">Clinical question</option></select></label>
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
                  </div></details>}
                  {editableDraft && block.evaluation.mode === "each_item" && <label className="type-label block max-w-xs">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.evaluation.collection || "findings"} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].evaluation.collection = event.target.value as NonNullable<RuleBlock["evaluation"]["collection"]> })}><option value="findings">Findings</option><option value="hrd">HRD</option><option value="msi">MSI</option><option value="tmb">TMB</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>}
                  {editableDraft && <label className="clinical-rule-action flex w-fit max-w-full items-center gap-2 rounded-lg px-2.5 py-1 text-sm" data-action="heading" data-active={block.show_heading} data-disabled={metadataOutput || block.section === "analysis_description"}><input type="checkbox" className="accent-warn" disabled={metadataOutput || block.section === "analysis_description"} checked={block.show_heading} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].show_heading = event.target.checked })} /> Show section heading</label>}
                  <div className="flex flex-wrap items-center gap-2" aria-label="Section rules">
                    {block.rules.map((item, index) => (
                      <Badge key={item.rule_id} variant={selectedRule === index ? "default" : "outline"} className={cn("max-w-full gap-0 whitespace-normal px-1 shadow-sm", selectedRule !== index && "bg-background")}>
                        <button type="button" aria-pressed={selectedRule === index} className="min-w-0 break-words rounded-full px-2 py-1 text-left type-body-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setSelectedRule(index)}>{item.name}</button>
                        {editableDraft && block.rules.length > 1 && <Button className="shrink-0 rounded-full" type="button" variant="ghost" size="icon-sm" title="Remove rule" onClick={() => mutateDraft((document) => { document.blocks[selectedBlock].rules.splice(index, 1); setSelectedRule(Math.max(0, Math.min(selectedRule - (index < selectedRule ? 1 : 0), document.blocks[selectedBlock].rules.length - 1))) })}><icon.trash2 /></Button>}
                      </Badge>
                    ))}
                    {editableDraft && <Button className="clinical-rule-action shrink-0 rounded-full" data-action="rule" variant="outline" size="sm" onClick={() => mutateDraft((document) => { const currentBlock = document.blocks[selectedBlock]; const allRuleIds = document.blocks.flatMap((item) => item.rules.map((itemRule) => itemRule.rule_id)); currentBlock.rules.push(newRule(currentBlock, allRuleIds)); setSelectedRule(currentBlock.rules.length - 1) })}><icon.plus /> Add rule</Button>}
                  </div>
                  {editableDraft && rule && <div className="flex flex-wrap items-center gap-2" aria-label="Rule order">
                    <span className="text-sm text-muted-foreground">Rule {selectedRule + 1} of {block.rules.length}</span>
                    {([-1, 1] as const).map(direction => <Button key={direction} type="button" variant="outline" size="sm" disabled={selectedRule + direction < 0 || selectedRule + direction >= block.rules.length} onClick={() => mutateDraft(document => {
                      const rules = document.blocks[selectedBlock].rules
                      const destination = selectedRule + direction
                      const [moved] = rules.splice(selectedRule, 1)
                      rules.splice(destination, 0, moved)
                      rules.forEach((item, index) => { item.order = (index + 1) * 10 })
                      setSelectedRule(destination)
                    })}>Move rule {direction === -1 ? "up" : "down"}</Button>)}
                    <p className="w-full type-meta text-muted-foreground">Rule order controls sentence order and precedence when using First match.</p>
                  </div>}
                </div>}
                {rule && block ? <fieldset disabled={!editableDraft}><RuleEditor readOnly={!editableDraft} rule={rule} block={block} facts={facts} controlledValues={controlledValues} terminology={draft.terminology} sentenceTerminology={optionsQuery.data?.sentence_terminology?.[draft.scope.language]} useTierSentences={() => {
                  setTextError("")
                  mutateDraft(document => {
                    const terms = optionsQuery.data?.sentence_terminology?.[document.scope.language]?.tier_summary
                    if (!document.terminology.tier_summary && terms) document.terminology.tier_summary = clone(terms)
                    document.blocks[selectedBlock].rules[selectedRule].output = [{ type: "renderer", name: "tier_summary" }]
                  })
                }} onTextError={setTextError} changeTerminology={(terms) => mutateDraft(document => { document.terminology = terms })} change={(next) => mutateDraft((document) => { document.blocks[selectedBlock].rules[selectedRule] = next })} /></fieldset> : <div className="grid min-h-72 place-items-center p-8 text-center"><div><p className="text-sm text-muted-foreground">This rule set does not have an authored section yet.</p>{editableDraft && <Button className="mt-3" variant="outline" onClick={() => mutateDraft((document) => document.blocks.push(newRuleBlock(document.blocks)))}><icon.plus /> Add first section</Button>}</div></div>}
              </div>
            </div>
            </div>
          </>}
        </main>
        <ResizeDivider label="Resize text preview" width={previewWidth} setWidth={setPreviewWidth} min={280} max={720} direction={-1} />
        <aside className="min-h-0 min-w-0 overflow-y-auto bg-muted/10 p-4">
          {draft ? <><div hidden={workspaceTab !== "report"}><RuleSetPreview key={draft._id} draft={draft} facts={facts} saved={workflowReady} canTest={can("clinical_rules:test")} /></div><div hidden={workspaceTab !== "annotation"}><BulkAnnotationPreview groups={annotationGroups} key={draft._id} documentId={draft._id} scopeDiagnosis={draft.scope.diagnosis_id} revision={draft.revision} saved={workflowReady} tier={annotationTier} /></div></> : <p className="type-body-sm text-muted-foreground">Select a rule set to preview its complete report wording.</p>}
          {editableDraft && workspaceTab === "report" && <section className="mt-5 border-t border-border pt-4"><h2 className="type-section-title">Report analyses</h2><div className="mt-2 space-y-2">{ANALYSES[draft.scope.analyte].map((analysis) => <label key={analysis} className="flex items-center justify-between gap-3 text-sm"><span>{analysis}</span><select className="paper-inset rounded-lg p-1.5 text-xs" value={draft.analysis_declarations[analysis]?.narrative || "undeclared"} onChange={(event) => mutateDraft((document) => { if (event.target.value === "undeclared") delete document.analysis_declarations[analysis]; else document.analysis_declarations[analysis] = { narrative: event.target.value as "enabled" | "none" } })}><option value="undeclared">Not declared</option><option value="enabled">Generate text</option><option value="none">No narrative</option></select></label>)}</div></section>}
        </aside>
      </div>
      {deletableVersion && !editableDraft && <Button variant="destructive" disabled={!workflowReady || deleteDraftMutation.isPending} onClick={() => setDeleteDraftOpen(true)}><icon.trash2 />Delete unpublished version</Button>}
      <ConfirmationDialog open={deleteDraftOpen} title="Delete unpublished version?" description="This permanently removes the selected pre-publication version and its private revision history. Published and retired versions are preserved. An audit receipt is retained." confirmLabel="Delete version" isPending={deleteDraftMutation.isPending} onConfirm={deleteDraft} onCancel={() => setDeleteDraftOpen(false)} />
    </PageShell>
  )
}
