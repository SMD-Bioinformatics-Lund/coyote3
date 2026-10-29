import { useRef, useState, type CSSProperties } from "react"
import { icon } from "@/lib/assets"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SearchInput } from "@/components/ui/search-input"
import { Badge } from "@/components/ui/badge"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { DocumentEditorNotice } from "@/components/admin/DocumentEditorNotice"
import { ConfigurationTransfer } from "@/components/admin/ConfigurationTransfer"
import { cn } from "@/lib/utils"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { QueryConditionBuilder } from "./QueryConditionBuilder"
import { QueryConditionSummary } from "./QueryConditionSummary"
import { QueryPolicyFlow, type PolicyResolution } from "./QueryPolicyFlow"
import { RecordProvenance } from "./RecordProvenance"
import { newQueryPredicate } from "./query-condition-types"
import type { QueryCondition, QueryConditionCatalog } from "./query-condition-types"
import { QueryConditionTestPanel } from "./QueryConditionTestPanel"
import { ClinicalRuleStatusBadge } from "./ClinicalRuleStatusBadge"
import { ResizeDivider } from "@/components/admin/RuleWorkspaceDivider"
import { useRuleWorkspaceLayout } from "@/hooks/useRuleWorkspaceLayout"

type Analysis = "snv" | "cnv" | "translocation" | "fusion"
type Exception = { id: string; mode: string; condition?: QueryCondition; [key: string]: unknown }
type Scope = { assay_group: string | null; asp_id: string | null; diagnosis_id: string | null; analysis: Analysis; intent: string; modality?: string | null; family?: string | null; environment?: string | null }
type Content = { evidence_mode: string | null; exceptions: Exception[] | null; exception_mode?: "replace" | "extend" }
type Draft = { name: string; reason: string; scope: Scope; content: Content }
export type Rule = Draft & { _id: string; version: number; revision: number; status: "draft" | "approved" | "published" | "retired"; created_by: string; approved_by?: string; system_installed?: boolean }
type Options = { groups: { id: string; name: string }[]; assays: { id: string; group: string; category: string; family?: string; diagnoses: string[] }[]; families?: { id: string; modality: string }[]; environments?: string[]; conditions?: QueryConditionCatalog }
type Resolution = PolicyResolution
const initial = (): Draft => ({ name: "", reason: "", scope: { assay_group: "", asp_id: null, diagnosis_id: null, analysis: "snv", intent: "somatic", modality: null, family: null, environment: null }, content: { evidence_mode: null, exceptions: null } })
const fields: Record<Analysis, string[]> = {
  snv: ["genes", "consequence_terms", "filter_values", "chromosomes", "position_min", "position_max", "simple_ids", "info_fields_present", "alt_regex"],
  cnv: ["genes", "callers", "effects", "chromosomes", "size_min", "size_max"],
  translocation: ["genes", "gene_pairs", "svtypes", "chromosomes"],
  fusion: ["genes", "gene_pairs", "callers", "effects", "descriptions"],
}
const control = "rounded-md border border-input bg-background px-3 py-2 text-foreground"
const label = (key: string) => key.replaceAll("_", " ").replace(/^./, text => text.toUpperCase())
const queryId = (scope: Scope) => [scope.assay_group || "default", scope.asp_id || "all", scope.diagnosis_id || "base", `${scope.intent}_${{ snv: "snvs", cnv: "cnvs", fusion: "fusions", translocation: "translocations" }[scope.analysis]}`, ...(scope.family ? [scope.modality, scope.family] : []), ...(scope.environment ? [scope.environment] : [])].join("__")

function InfoEqualityEditor({ value, onChange }: { value: Record<string, string | number | boolean>; onChange: (value: Record<string, string | number | boolean>) => void }) {
  const entries = Object.entries(value)
  const update = (index: number, key: string, item: string | number | boolean) => {
    if (entries[index][0] !== key && key in value) return
    onChange(Object.fromEntries(entries.map((row, i) => i === index ? [key, item] : row)))
  }
  return <fieldset className="space-y-2">
    <legend>Exact INFO values</legend>
    <p className="text-muted-foreground">Every named field must equal its typed value.</p>
    {entries.map(([key, item], index) => <div key={index} className="grid gap-2 md:grid-cols-4">
      <Input aria-label={`INFO field ${index + 1}`} value={key} onChange={e => update(index, e.target.value, item)} />
      <select aria-label={`INFO value type ${index + 1}`} className={control} value={typeof item} onChange={e => update(index, key, e.target.value === "number" ? 0 : e.target.value === "boolean" ? false : "")}><option value="string">Text</option><option value="number">Number</option><option value="boolean">Boolean</option></select>
      {typeof item === "boolean" ? <select aria-label={`INFO value ${index + 1}`} className={control} value={String(item)} onChange={e => update(index, key, e.target.value === "true")}><option value="false">False</option><option value="true">True</option></select> : <Input aria-label={`INFO value ${index + 1}`} type={typeof item === "number" ? "number" : "text"} value={item} onChange={e => update(index, key, typeof item === "number" ? Number(e.target.value) : e.target.value)} />}
      <Button variant="outline" onClick={() => onChange(Object.fromEntries(entries.filter((_, i) => i !== index)))}>Remove INFO field</Button>
    </div>)}
    <Button variant="outline" onClick={() => { let key = "FIELD"; while (key in value) key += "_NEW"; onChange({ ...value, [key]: "" }) }}>Add INFO field</Button>
  </fieldset>
}

function PolicySummary({ title, value, analysis, compact = false }: { title: string; value?: Resolution; analysis: Analysis; compact?: boolean }) {
  return <section className="surface-panel rounded-lg border p-4 space-y-3">
    <h2 className="type-section-title">{title}</h2>
    {!value ? <p className="text-muted-foreground">Choose a scope and preview its policy.</p> : <>
      {compact ? <>
        {value.evidence_mode && <p className="type-supporting">Evidence: {label(value.evidence_mode)}</p>}
        {value.exceptions.map(rule => <details key={rule.id}><summary className="cursor-pointer type-label">{rule.id} · {label(rule.mode)}</summary>
          {rule.condition ? <QueryConditionSummary condition={rule.condition} /> : <pre className="overflow-auto type-supporting">{JSON.stringify(rule, null, 2)}</pre>}
        </details>)}
        <p className="type-supporting text-muted-foreground">Use Preview effective policy to inspect the complete flow and source settings.</p>
      </> : <QueryPolicyFlow value={value} analysis={analysis} />}
    </>}
  </section>
}

export function QueryRulesPage() {
  const client = useQueryClient()
  const { data: access } = useCurrentUserAccess()
  const [draft, setDraft] = useState<Draft>(initial)
  const [selected, setSelected] = useState<Rule | null>(null)
  const [activeSection, setActiveSection] = useState("scope")
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [groupFilter, setGroupFilter] = useState("")
  const { listCollapsed, setListCollapsed, listWidth, setListWidth, previewWidth, setPreviewWidth }
    = useRuleWorkspaceLayout("query")
  const [baseline, setBaseline] = useState<Resolution>()
  const [preview, setPreview] = useState<Resolution>()
  const [previewTab, setPreviewTab] = useState<"draft" | "published">("draft")
  const parent = useQuery({ queryKey: ["query-rule-parent", draft.scope], enabled: draft.scope.assay_group !== "", queryFn: () => api.post<Resolution>("/admin/query-rule-sets/preview", { scope: draft.scope, content: { evidence_mode: null, exceptions: null } }).then(r => r.data) })
  const [dirty, setDirty] = useState(false)
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty || Boolean(draft.reason)
  const previewGeneration = useRef(0)
  const [confirmation, setConfirmation] = useState<{ title: string; description: string; run: () => void } | null>(null)
  const list = useQuery({ queryKey: ["query-rules"], queryFn: () => api.get<{ items: Rule[] }>("/admin/query-rule-sets").then(r => r.data) })
  const options = useQuery({ queryKey: ["query-rule-options"], queryFn: () => api.get<Options>("/admin/query-rule-sets/options").then(r => r.data) })
  const [historyOpen, setHistoryOpen] = useState(false)
  const history = useQuery({ queryKey: ["query-rule-revisions", selected?._id, selected?.revision], enabled: historyOpen && !!selected, queryFn: () => api.get<{ revision: number; action: string; actor: string; occurred_at: string; document: Rule }[]>(`/admin/query-rule-sets/${selected!._id}/revisions`).then(r => r.data) })
  const documentEditor = useDocumentEditor("query-rules", selected?._id || "", Boolean(selected?.status === "draft" && !selected.system_installed && hasPermission(access, "query_rules:draft")))
  const editable = documentEditor.owned && hasPermission(access, "query_rules:draft") && !selected?.system_installed && (!selected || selected.status === "draft")
  const change = (next: Draft) => { previewGeneration.current++; setDraft(next); setDirty(true); setPreview(undefined); setBaseline(undefined) }
  const choose = (rule: Rule | null) => { previewGeneration.current++; setSelected(rule); setActiveSection("scope"); setDraft(rule ? structuredClone({ name: rule.name, reason: "", scope: rule.scope, content: rule.content }) : initial()); setDirty(false); setPreview(undefined); setBaseline(undefined) }
  const selectVersion = (rule: Rule | null) => {
    if (!dirty) choose(rule)
    else setConfirmation({ title: "Discard unsaved changes?", description: "The saved version remains unchanged.", run: () => choose(rule) })
  }
  const importDraft = async (document: Record<string, unknown>) => {
    if (!document.scope || typeof document.scope !== "object" || Array.isArray(document.scope)
      || !document.content || typeof document.content !== "object" || Array.isArray(document.content)
      || typeof document.name !== "string") throw new Error("Provide a query-rule name, scope and content")
    const generation = previewGeneration.current
    const { data: validated } = await api.post<{ scope: Scope }>("/admin/query-rule-sets/preview",
      { scope: document.scope, content: document.content }, { errorNotice: "inline" })
    if (generation !== previewGeneration.current) throw new Error("The draft changed while checking the file. Import it again.")
    const run = () => {
      choose(null)
      change({ name: document.name as string, scope: validated.scope,
        content: { ...initial().content, ...document.content as Content }, reason: "" })
    }
    if (dirtyRef.current) setConfirmation({ title: "Discard unsaved changes?", description: "Import this policy into a new unsaved draft.", run })
    else run()
  }
  const mutation = useMutation({
    mutationFn: async (action: string) => {
      if (action === "save") return selected
        ? (await api.put<Rule>(`/admin/query-rule-sets/${selected._id}`, { ...draft, expected_revision: selected.revision }, documentEditor.options())).data
        : (await api.post<Rule>("/admin/query-rule-sets", draft)).data
      if (!selected) throw new Error("Select a saved version first")
      return (await api.post<Rule>(`/admin/query-rule-sets/${selected._id}/${action}`, { expected_revision: selected.revision, reason: draft.reason }, documentEditor.options())).data
    },
    onSuccess: result => {
      choose(result)
      void client.invalidateQueries({ queryKey: ["query-rules"] })
      if (result.status === "published" || result.status === "retired") {
        for (const key of ["sample-variants", "sample-cnvs", "sample-fusions", "sample-translocations", "sample-rna-analysis", "sample-comment-suggestion", "report-preview"]) {
          void client.invalidateQueries({ queryKey: [key] })
        }
      }
      notifySuccess("Query policy saved", `${result.name} · ${result.status}`, "Query rules")
    },
    onError: error => notifyActionError("Unable to save query policy", error, "Query rules"),
  })
  const deletion = useMutation({
    mutationFn: () => api.delete(`/admin/query-rule-sets/${selected!._id}`, { ...documentEditor.options(), body: JSON.stringify({ expected_revision: selected!.revision, reason: draft.reason }) }),
    onSuccess: () => { choose(null); void client.invalidateQueries({ queryKey: ["query-rules"] }); notifySuccess("Unpublished version deleted", "Published policies are unchanged.", "Query rules") },
    onError: error => notifyActionError("Unable to delete version", error, "Query rules"),
  })
  const inspect = useMutation({
    mutationFn: async () => {
      const generation = previewGeneration.current
      const [current, proposed] = await Promise.all([
        api.post<Resolution>("/admin/query-rule-sets/preview", { scope: draft.scope }),
        api.post<Resolution>("/admin/query-rule-sets/preview", { scope: draft.scope, content: draft.content }),
      ])
      return { current: current.data, proposed: proposed.data, generation }
    },
    onSuccess: data => { if (data.generation === previewGeneration.current) { setBaseline(data.current); setPreview(data.proposed) } },
    onError: error => notifyActionError("Unable to preview query policy", error, "Query rules"),
  })
  const scopeChange = (scope: Scope) => change({ ...draft, scope: { ...scope, ...(!scope.assay_group || scope.asp_id ? { modality: null, family: null } : {}) } })
  const exceptionChange = (index: number, value: Exception) => change({ ...draft, content: { ...draft.content, exceptions: draft.content.exceptions!.map((rule, i) => i === index ? value : rule) } })
  const changeExceptionMode = (mode: string) => {
    const run = () => change({ ...draft, content: { ...draft.content, exception_mode: mode === "extend" ? "extend" : "replace", exceptions: mode === "inherit" ? null : draft.content.exceptions ?? [] } })
    if (mode === "inherit" && draft.content.exceptions?.length) setConfirmation({ title: "Discard this scope’s conditions?", description: "Switching to inheritance removes the local exception list from this draft. Cancel to keep editing it. Published rules are unchanged until a replacement version is approved and published.", run })
    else run()
  }
  const assays = (options.data?.assays ?? []).filter(a => a.group === draft.scope.assay_group && a.category === (draft.scope.analysis === "fusion" ? "rna" : "dna")).sort((a, b) => a.id.localeCompare(b.id))
  const diagnoses = [...new Set(assays.filter(a => (!draft.scope.asp_id || a.id === draft.scope.asp_id) && (!draft.scope.family || a.family === draft.scope.family)).flatMap(a => a.diagnoses))].filter(id => id !== "base").sort((a, b) => a.localeCompare(b))
  const addCondition = () => {
    const catalog = options.data?.conditions
    if (!catalog) return
    change({ ...draft, content: { ...draft.content, exception_mode: draft.content.exceptions === null ? "extend" : draft.content.exception_mode, exceptions: [...(draft.content.exceptions ?? []), { id: "", mode: "exclude", condition: newQueryPredicate(catalog.fields[draft.scope.analysis]) }] } })
  }
  const visibleRules = (list.data?.items ?? []).filter(rule => {
    const groupName = options.data?.groups.find(group => group.id === rule.scope.assay_group)?.name ?? ""
    const searchable = [rule.name, groupName, rule.scope.assay_group, rule.scope.asp_id, rule.scope.diagnosis_id, rule.scope.analysis, rule.scope.intent, rule.scope.family, rule.scope.environment].join(" ").toLowerCase()
    return (!statusFilter || rule.status === statusFilter) && (!groupFilter || (rule.scope.assay_group ?? "__default__") === groupFilter) && searchable.includes(search.trim().toLowerCase())
  })
  return <PageShell eyebrow="Finding selection" title="Query rules" description="Author, review and publish finding-selection policies for groups, assays and diagnoses."
    actions={<>{dirty && <Badge variant="outline">Unsaved</Badge>}{hasPermission(access, "query_rules:test") && <Button variant="outline" nativeButton={false} render={<Link to={selected ? `/admin/query-rules/testing?version=${encodeURIComponent(selected._id)}` : "/admin/query-rules/testing"} />}><icon.beaker />Test rules</Button>}<Button variant="outline" onClick={() => selectVersion(null)} disabled={mutation.isPending || !hasPermission(access, "query_rules:draft")}><icon.plus />New scope version</Button></>}>
    <DocumentEditorNotice editor={documentEditor} />
    <ConfigurationTransfer label="query rules" filename={selected ? `${selected.name}-query-rules` : "query-rules"}
      document={selected ? { name: selected.name, scope: selected.scope, content: selected.content } : undefined}
      onImport={hasPermission(access, "query_rules:draft") ? importDraft : undefined}
      fields={["name", "scope", "content"]} required={["name", "scope", "content"]}
      disabled={mutation.isPending || deletion.isPending} />
    {(list.isError || options.isError) && <p role="alert">Unable to load query rules. Refresh to retry.</p>}
    <div className={cn("query-rules-layout clinical-rules-workspace surface-panel overflow-hidden", listCollapsed && "is-rule-list-collapsed")} style={{ "--rule-list-width": `${listWidth}px`, "--preview-width": `${previewWidth}px` } as CSSProperties}>
      <aside className="flex min-h-0 min-w-0 flex-col border-b border-border xl:border-b-0" aria-label="Query-rule navigation">
        {listCollapsed ? <button type="button" className="clinical-rules-rail" aria-label="Expand query-rule list" onClick={() => setListCollapsed(false)}><icon.panelLeftOpen /><span>Rule sets</span></button> : <>
          <div className="space-y-2 border-b border-border p-3">
            <div className="flex items-center gap-1">
              <SearchInput aria-label="Search query rules" placeholder="Search rules" value={search} onChange={event => setSearch(event.target.value)} />
              <Button size="icon-sm" variant="ghost" aria-label="Collapse query-rule list" title="Collapse query-rule list" onClick={() => setListCollapsed(true)}><icon.panelLeftClose /></Button>
            </div>
            <label className="block type-meta text-muted-foreground">Workflow state<select aria-label="Filter query rules by workflow state" className="paper-inset mt-1 w-full rounded-lg p-2 type-body-sm text-foreground" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All workflow states</option>{["draft", "approved", "published", "retired"].map(status => <option key={status} value={status}>{label(status)}</option>)}</select></label>
            <select aria-label="Filter query rules by assay group" className="paper-inset w-full rounded-lg p-2 type-supporting" value={groupFilter} onChange={event => setGroupFilter(event.target.value)}><option value="">All assay groups</option><option value="__default__">Default: all groups</option>{options.data?.groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select>
            <p className="type-supporting text-muted-foreground" role="status">{visibleRules.length} of {list.data?.items.length ?? 0} versions</p>
          </div>
          <nav className="min-h-0 max-h-96 flex-1 overflow-y-auto p-2 xl:max-h-none" aria-label="Query rule sets">
            {list.isLoading ? <p className="p-3 type-body-sm text-muted-foreground">Loading…</p> : !list.data?.items.length ? <p className="p-3 type-body-sm text-muted-foreground">No published overrides. Default policies apply.</p> : !visibleRules.length ? <p className="p-3 type-body-sm text-muted-foreground">No versions match these filters.</p> : visibleRules.map(rule => <button type="button" key={rule._id} disabled={mutation.isPending} aria-pressed={selected?._id === rule._id} className={cn("mb-2 w-full rounded-lg border px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60", selected?._id === rule._id ? "border-primary/40 bg-primary/10" : "border-border bg-card hover:border-primary/30 hover:bg-muted")} onClick={() => selectVersion(rule)}>
              <span className="block truncate type-body-sm font-semibold" title={rule.name}>{rule.name}</span>
              <span className="mt-0.5 block truncate type-meta text-muted-foreground" title={`${rule.scope.assay_group ?? "All groups"} / ${rule.scope.asp_id ?? "All assays"} / ${rule.scope.diagnosis_id ?? "All diagnoses"}`}>{rule.scope.assay_group ?? "Default: all groups"} · {rule.scope.asp_id ?? "All assays"} · {rule.scope.diagnosis_id ?? "All diagnoses"}</span>
              <span className="mt-1.5 flex flex-wrap items-center justify-between gap-1.5"><span className="type-meta text-muted-foreground">{rule.scope.analysis.toUpperCase()} · {label(rule.scope.intent)}</span><ClinicalRuleStatusBadge status={rule.status} prefix={`v${rule.version} `} /></span>
              {rule.system_installed && <span className="mt-0.5 block"><RecordProvenance record={rule} /></span>}
            </button>)}
          </nav>
        </>}
      </aside>
      {!listCollapsed && <ResizeDivider label="Resize query-rule list" width={listWidth} setWidth={setListWidth} min={210} max={440} />}
      <section className="flex min-h-0 min-w-0 flex-col" aria-label="Query-rule editor">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border bg-muted/35 p-3">
          <div className="min-w-0 flex-1"><h2 className="break-words font-semibold">{selected ? selected.name : "New draft"}</h2><p className="mt-1 type-supporting text-muted-foreground">{selected ? `Version ${selected.version} · revision ${selected.revision}` : "Choose a scope and define its selection policy."}</p></div>
          <div className="flex items-center gap-2">{selected && !editable && <Badge variant="outline">Read-only</Badge>}{selected && <ClinicalRuleStatusBadge status={selected.status} />}</div>
        </div>
        <div className="border-b border-border bg-muted/15 p-3 space-y-2">
        <label className="block type-body-sm">Change or review reason<Input value={draft.reason} onChange={e => setDraft({ ...draft, reason: e.target.value })} /></label>
        <div className="flex flex-wrap gap-2">
          {editable && <Button size="sm" disabled={mutation.isPending || !draft.reason.trim() || draft.scope.assay_group === ""} onClick={() => mutation.mutate("save")}>Save draft</Button>}
          {selected && !selected.system_installed && ["draft", "approved"].includes(selected.status) && hasPermission(access, "query_rules:draft") && <Button size="sm" variant="outline" disabled={mutation.isPending || deletion.isPending || !draft.reason.trim()} onClick={() => setConfirmation({ title: "Delete this unpublished version?", description: "This permanently removes the selected version and its private revision snapshots. Published rules remain unchanged. The deletion reason is retained in the audit log.", run: () => deletion.mutate() })}>Delete version</Button>}
          {selected && !selected.system_installed && [["draft", "approve", "review"], ["approved", "publish", "publish"], ["published", "retire", "retire"]].map(([status, action, permission]) => selected.status === status && hasPermission(access, `query_rules:${permission}`) && <Button size="sm" key={action} disabled={dirty || mutation.isPending || !draft.reason.trim()} onClick={() => setConfirmation({ title: `${label(action)} this saved version?`, description: action === "retire" ? "Parent policy will apply." : action === "publish" ? "This changes live finding retrieval for this scope and inheriting children." : "Confirm independent clinical review.", run: () => mutation.mutate(action) })}>{label(action)}</Button>)}
        </div>
        <nav aria-label="Query definition sections" className="flex flex-wrap gap-1 pt-2">
          {[{ id: "scope", title: "Scope and inheritance" }, { id: "conditions", title: `Conditions (${draft.content.exceptions?.length ?? 0})` }].map(section => <Button size="sm" variant={activeSection === section.id ? "secondary" : "ghost"} aria-pressed={activeSection === section.id} key={section.id} onClick={() => setActiveSection(section.id)}>{section.title}</Button>)}
        </nav>
        </div>
        <div className="min-h-0 min-w-0 flex-1 space-y-4 overflow-y-auto p-4">
        {selected && <p className="type-supporting text-muted-foreground">The scope of a saved version is fixed. Select New scope version to choose another group, assay or diagnosis.</p>}
        {selected && selected.status !== "draft" && <Button disabled={!hasPermission(access, "query_rules:draft")} onClick={() => { setSelected(null); setDirty(true); setDraft({ ...draft, reason: "" }) }}>Copy to new draft version</Button>}
        {!editable && selected ? <section className="space-y-4" aria-label="Saved query definition">
          <dl hidden={activeSection !== "scope"} className="grid gap-3 rounded-lg border bg-background p-4 sm:grid-cols-2">
            {Object.entries({ "Query ID": queryId(draft.scope), Analysis: draft.scope.analysis.toUpperCase(), Intent: label(draft.scope.intent), "Assay group": draft.scope.assay_group ?? "All groups", Family: draft.scope.family ?? "All families", Environment: draft.scope.environment ?? "Shared across environments", Assay: draft.scope.asp_id ?? "All assays", Diagnosis: draft.scope.diagnosis_id ?? "All diagnoses", ...(draft.content.evidence_mode ? { "Evidence mode": label(draft.content.evidence_mode) } : {}), Exceptions: draft.content.exceptions === null ? "Inherit parent" : draft.content.exception_mode === "extend" ? "Inherit and add" : "Replace parent list" }).map(([key, value]) => <div key={key} className="min-w-0"><dt className="type-label text-muted-foreground">{key}</dt><dd className="mt-1 break-words type-supporting">{value}</dd></div>)}
          </dl>
          {(draft.content.exceptions === null || draft.content.exception_mode === "extend") && <PolicySummary title="Inherited policy" value={parent.data} analysis={draft.scope.analysis} compact />}
          {draft.content.exceptions?.map(rule => <section hidden={activeSection !== "conditions"} key={rule.id} className="space-y-3 rounded-lg border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold break-words">{rule.id}</h3><Badge variant="outline">{label(rule.mode)}</Badge></div>
            {rule.condition && <QueryConditionSummary condition={rule.condition} />}
            {Object.entries(rule).filter(([key, value]) => !["id", "mode", "condition"].includes(key) && value !== null && value !== undefined).map(([key, value]) => <dl key={key}><dt className="type-label text-muted-foreground">{label(key)}</dt><dd className="break-words type-supporting">{JSON.stringify(value)}</dd></dl>)}
          </section>)}
          {draft.content.exceptions?.length === 0 && <p className="type-supporting text-muted-foreground">No local exceptions are defined.</p>}
        </section> : <fieldset disabled={!editable || mutation.isPending} className="space-y-4">
          <div hidden={activeSection !== "scope"} className="space-y-4">
          <label className="block">Query ID<Input readOnly value={draft.scope.assay_group === "" ? "" : queryId(draft.scope)} placeholder="Select a scope to generate the query ID" /></label>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1">Analysis<select className={control} disabled={!!selected} value={draft.scope.analysis} onChange={e => change({ ...draft, scope: { ...draft.scope, analysis: e.target.value as Analysis, intent: "somatic", asp_id: null, diagnosis_id: null, modality: null, family: null }, content: { evidence_mode: null, exceptions: null } })}>{Object.keys(fields).map(key => <option key={key} value={key}>{key.toUpperCase()}</option>)}</select></label>
            <label className="flex flex-col gap-1">Intent<select className={control} disabled={!!selected || draft.scope.analysis !== "snv"} value={draft.scope.intent} onChange={e => scopeChange({ ...draft.scope, intent: e.target.value })}><option value="somatic">Somatic</option><option value="germline">Germline</option></select></label>
            <label className="flex flex-col gap-1">Assay group<select className={control} disabled={!!selected} value={draft.scope.assay_group ?? "__all_groups__"} onChange={e => scopeChange({ ...draft.scope, assay_group: e.target.value === "__all_groups__" ? null : e.target.value, asp_id: null, diagnosis_id: null })}><option value="">Select scope</option><option value="__all_groups__">Default: all assay groups</option>{options.data?.groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
            <label className="flex flex-col gap-1">Assay<select className={control} disabled={!!selected || !draft.scope.assay_group} value={draft.scope.asp_id ?? ""} onChange={e => scopeChange({ ...draft.scope, asp_id: e.target.value || null, diagnosis_id: null })}><option value="">All assays in group</option>{assays.map(a => <option key={a.id} value={a.id}>{a.id}</option>)}</select></label>
            <label className="flex flex-col gap-1">Family<select className={control} disabled={!!selected || !draft.scope.assay_group || !!draft.scope.asp_id} value={draft.scope.family ?? ""} onChange={e => scopeChange({ ...draft.scope, family: e.target.value || null, modality: e.target.value ? (draft.scope.analysis === "fusion" ? "rna" : "dna") : null, diagnosis_id: null })}><option value="">All families</option>{options.data?.families?.filter(f => f.modality === (draft.scope.analysis === "fusion" ? "rna" : "dna")).map(f => <option key={f.id} value={f.id}>{f.id.toUpperCase()}</option>)}</select></label>
            <label className="flex flex-col gap-1">Environment<select className={control} disabled={!!selected} value={draft.scope.environment ?? ""} onChange={e => scopeChange({ ...draft.scope, environment: e.target.value || null })}><option value="">Shared across environments</option>{options.data?.environments?.map(environment => <option key={environment} value={environment}>{label(environment)}</option>)}</select></label>
            <label className="flex flex-col gap-1">Diagnosis<select className={control} disabled={!!selected || !draft.scope.assay_group} value={draft.scope.diagnosis_id ?? ""} onChange={e => scopeChange({ ...draft.scope, diagnosis_id: e.target.value || null })}><option value="">All diagnoses in scope</option>{diagnoses.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
            {draft.scope.analysis === "snv" && <label className="flex flex-col gap-1">Evidence mode<select className={control} value={draft.content.evidence_mode ?? ""} onChange={e => change({ ...draft, content: { ...draft.content, evidence_mode: e.target.value || null } })}><option value="">Inherit parent</option>{["paired", "case_only", "exception_only"].map(mode => <option key={mode} value={mode}>{label(mode)}</option>)}</select></label>}
          </div>
          {draft.scope.analysis === "snv" && <p className="type-supporting text-muted-foreground">Transitional SNV workflow: published germline exceptions also apply to somatic SNV selection. Test either intent’s rules against the sample’s somatic SNV results. A germline rule’s evidence mode does not replace somatic evidence settings.</p>}
          <p className="type-supporting text-muted-foreground">Policies apply in order: center, group, family, diagnosis, diagnosis and family, assay, diagnosis and assay. At each level, the selected environment overrides shared settings. Diagnosis policies can span several assays in the group.</p>
          {draft.scope.assay_group && !assays.length && !options.isLoading && <p role="status" className="type-supporting text-muted-foreground">No active assays match this group and analysis. A group-wide policy can still be defined.</p>}
          {draft.scope.analysis === "snv" && <p className="type-supporting text-muted-foreground">{draft.content.evidence_mode === "paired" ? "Paired: require case evidence and check control evidence when present, plus population-frequency limits and eligible consequences. Records without a control remain eligible. This does not create or pair samples." : draft.content.evidence_mode === "case_only" ? "Case only: accept a genotype meeting case thresholds, without requiring a case role label or checking control evidence. Population-frequency limits and eligible consequences still apply." : draft.content.evidence_mode === "exception_only" ? "Exception only: omit the ordinary evidence branch. Only matching admission exceptions can admit findings; without them no findings are admitted." : "Inherit parent: use the nearest published ancestor’s evidence setting-assay, group, default-then the application default. Preview effective policy shows the selected sources."}</p>}
          </div>
          <section hidden={activeSection !== "conditions"} className="space-y-3 rounded-lg border p-4" aria-label="Conditions">
          <h3 className="type-section-title">Conditions</h3>
          <label className="flex flex-col gap-1">Exception list<select className={control} value={draft.content.exceptions === null ? "inherit" : draft.content.exception_mode ?? "replace"} onChange={e => changeExceptionMode(e.target.value)}><option value="inherit">Inherit parent exceptions</option><option value="extend">Inherit and add exceptions</option><option value="replace">Replace inherited exceptions</option></select></label>
          <p className="text-muted-foreground">Inherited rules are read-only. Additions use unique identifiers and run alongside parent rules; exclusions take precedence. To redefine a parent rule, choose Replace inherited exceptions and define the complete local list.</p>
          {(draft.content.exceptions === null || draft.content.exception_mode === "extend") && <PolicySummary title="Parent rules · read-only" value={parent.data} analysis={draft.scope.analysis} compact />}
          {parent.isError && <p role="alert">Unable to load parent rules. Retry the policy preview before saving.</p>}
          {!options.data?.conditions && <p role="status">{options.isLoading ? "Loading condition fields…" : "Condition fields are unavailable. Refresh to load the editor."}</p>}
          {draft.content.exceptions !== null && <>
            <p className="text-muted-foreground">{draft.content.exception_mode === "extend" ? "These local exceptions are added to the parent list. An empty list keeps all inherited exceptions." : "This complete list replaces inherited exceptions. An empty list removes them."} Each exception can contain nested logical groups. Additional field criteria are combined with its condition tree using AND.</p>
            {options.data?.conditions && <p className="text-muted-foreground type-supporting">Each tree supports up to {options.data.conditions.max_depth} levels and {options.data.conditions.max_nodes} conditions; value lists accept up to {options.data.conditions.max_list_values} entries. Field names and operators are supplied by the application contract.</p>}
            {draft.content.exceptions.map((rule, index) => <fieldset key={index} className="min-w-0 rounded-lg border bg-background p-4 space-y-4">
              <legend>Exception {index + 1}</legend>
              <div className="grid items-start gap-3 md:grid-cols-2">
              <label className="block">Identifier<Input value={rule.id} onChange={e => exceptionChange(index, { ...rule, id: e.target.value })} /></label>
              <label className="flex flex-col gap-1">Action<select className={control} value={rule.mode} onChange={e => exceptionChange(index, { ...rule, mode: e.target.value })}>{["admit", "exclude", ...(draft.scope.analysis === "snv" ? ["extend_consequence"] : [])].map(mode => <option key={mode} value={mode}>{label(mode)}</option>)}</select></label>
              </div>
              {options.data?.conditions && (rule.condition
                ? <><QueryConditionBuilder key={`${selected?._id ?? "new"}:${index}`} value={rule.condition} fields={options.data.conditions.fields[draft.scope.analysis]} catalog={options.data.conditions} onChange={condition => exceptionChange(index, { ...rule, condition })} /><Button variant="outline" onClick={() => { const next = { ...rule }; delete next.condition; exceptionChange(index, next) }}>Remove condition tree</Button></>
                : <Button variant="outline" onClick={() => exceptionChange(index, { ...rule, condition: newQueryPredicate(options.data!.conditions!.fields[draft.scope.analysis]) })}>Add condition tree</Button>)}
              <details open={!rule.condition} className="rounded-lg border p-3"><summary className="cursor-pointer type-label">Additional field criteria (AND)</summary>
              <div className="grid gap-3 md:grid-cols-2">{fields[draft.scope.analysis].map(key => <label key={key} className="block">{label(key)}<Input placeholder={/_min$|_max$/.test(key) ? "Not specified" : key === "alt_regex" ? "Optional pattern" : "Comma-separated values"} value={Array.isArray(rule[key]) ? (rule[key] as string[]).join(", ") : String(rule[key] ?? "")} onChange={e => {
                const next = { ...rule }; const value = e.target.value;
                if (!value) delete next[key]; else next[key] = /_min$|_max$/.test(key) ? Number(value) : key === "alt_regex" ? value : value.split(",").map(v => v.trim());
                exceptionChange(index, next)
              }} /></label>)}</div>
              {draft.scope.analysis === "snv" && <InfoEqualityEditor value={(rule.info_equals ?? {}) as Record<string, string | number | boolean>} onChange={value => exceptionChange(index, { ...rule, info_equals: value })} />}
              </details>
              <Button variant="outline" onClick={() => change({ ...draft, content: { ...draft.content, exceptions: draft.content.exceptions!.filter((_, i) => i !== index) } })}>Remove exception</Button>
            </fieldset>)}
          </>}
          <Button variant="outline" disabled={!options.data?.conditions} onClick={addCondition}>Add condition</Button>
          </section>
        </fieldset>}
        {editable && <details><summary className="cursor-pointer type-label">Advanced: synthetic condition examples</summary><QueryConditionTestPanel analysis={draft.scope.analysis} conditions={(draft.content.exceptions ?? []).flatMap(rule => rule.condition ? [{ id: rule.id, condition: rule.condition }] : [])} /></details>}
        </div>
      </section>
      <ResizeDivider label="Resize query preview" width={previewWidth} setWidth={setPreviewWidth} min={280} max={600} direction={-1} />
      <aside className="min-h-0 min-w-0 space-y-4 overflow-y-auto border-t border-border p-4 xl:border-t-0" aria-label="Query policy preview">
        <h2 className="type-section-title">Effective query policy</h2>
        <p className="type-body-sm text-muted-foreground">Follow application defaults through inherited and overridden rules to the final selection flow. Preview updates include your unsaved edits.</p>
        <Button variant="outline" disabled={draft.scope.assay_group === "" || inspect.isPending} onClick={() => inspect.mutate()}>Preview effective policy</Button>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Policy comparison">
          <Button size="sm" variant={previewTab === "draft" ? "default" : "outline"} aria-pressed={previewTab === "draft"} onClick={() => setPreviewTab("draft")}>{editable ? "Draft result" : "Selected version"}</Button>
          <Button size="sm" variant={previewTab === "published" ? "default" : "outline"} aria-pressed={previewTab === "published"} onClick={() => setPreviewTab("published")}>Currently published</Button>
        </div>
        <PolicySummary title={previewTab === "published" ? "Currently published" : editable ? "Draft result" : "Selected version"} value={previewTab === "published" ? baseline : preview} analysis={draft.scope.analysis} />
        {selected && <details onToggle={event => setHistoryOpen(event.currentTarget.open)}><summary className="cursor-pointer type-label">Revision history</summary>{history.isLoading ? <p>Loading revisions…</p> : history.isError ? <p role="alert">Unable to verify revision history.</p> : history.data?.map(row => <details key={row.revision} className="rounded border p-3"><summary className="cursor-pointer">Revision {row.revision} · {row.action} · {row.actor} · {row.occurred_at}</summary><pre className="overflow-auto text-sm">{JSON.stringify(row.document, null, 2)}</pre></details>)}</details>}
      </aside>
    </div>
    <ConfirmationDialog open={confirmation !== null} title={confirmation?.title ?? "Confirm"} description={confirmation?.description ?? ""} onCancel={() => setConfirmation(null)} onConfirm={() => { confirmation?.run(); setConfirmation(null) }} />
  </PageShell>
}
