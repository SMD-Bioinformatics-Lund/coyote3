import { useState } from "react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, Check, ClipboardCheck, Dna, Edit, FileCheck, Layers, ListTree, Plus, RefreshCw, Save, Settings2, Trash2 } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { cn } from "@/lib/utils"
import { AdminManagedForm } from "./resource-form"
import { formStateFromSpec, submitPayload } from "./resource-list"
import { specs, type FormSpec } from "./resource-specs"

type Document = Record<string, unknown>
type Content = { panel: Document; scopes: string[]; environments: string[]; gene_lists: Document[]; configurations: Document[] }
type Setup = { _id: string; asp_id: string; status: "draft" | "submitted" | "published"; revision: number; content: Content; content_editors: string[]; created_by: string; updated_by: string; review_reason: string }
type Context = {
  setup?: Setup
  panel_form: FormSpec
  genelist_form?: FormSpec
  configuration_form?: FormSpec
  subpanels: { subpanel_id: string; display_name: string; is_active: boolean }[]
  environments: string[]
  rules?: { _id: string; rule_set_id: string; name: string; content_version: number; scope: { subpanel_id: string } }[]
  readiness?: { ready: boolean; issues: string[] }
  context_error?: string
  history?: { revision: number; action: string; actor: string; at: string }[]
}
const steps = [
  { name: "Assay", icon: Dna }, { name: "Scopes", icon: Layers },
  { name: "Gene lists", icon: ListTree }, { name: "Reporting rules", icon: FileCheck },
  { name: "Configurations", icon: Settings2 }, { name: "Review", icon: ClipboardCheck },
]
const emptyContent = (panel: Document): Content => ({ panel, scopes: ["base"], environments: [], gene_lists: [], configurations: [] })
const writePermissions = ["assay.panel:create", "assay.panel:edit", "assay.config:create", "gene_list.insilico:create"]

function ResourceEditor({ kind, form, source, readonly, pending, onSave, onCancel }: {
  kind: "asp" | "aspc" | "genelists"; form: FormSpec; source: Document; readonly: boolean; pending: boolean
  onSave: (document: Document) => void; onCancel: () => void
}) {
  const [values, setValues] = useState(() => formStateFromSpec(form, source))
  const [error, setError] = useState("")
  const stagedForm = { ...form, fields: { ...form.fields, is_active: { ...form.fields.is_active, hidden_mode: ["create", "view"] } } }
  return <AdminManagedForm mode={readonly ? "view" : "create"} spec={specs[kind]} form={stagedForm} values={values} setValues={setValues} isSaving={pending} error={error} onCancel={onCancel} onSave={() => {
    try { onSave(submitPayload(form, values, "create")) } catch (err) { setError(err instanceof Error ? err.message : "Check the form values") }
  }} />
}

function ScopeEditor({ content, context, readonly, pending, onSave, onRefresh }: { content: Content; context: Context; readonly: boolean; pending: boolean; onSave: (content: Content) => void; onRefresh: () => void }) {
  const [scopes, setScopes] = useState(content.scopes)
  const [environments, setEnvironments] = useState(content.environments)
  const toggle = (items: string[], value: string) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
  return <section className="surface-panel space-y-5 p-4">
    {!readonly && <div className="flex flex-wrap items-center justify-end gap-3"><Link to="/admin/subpanels" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-primary underline"><Layers className="size-4" />Manage subpanel definitions</Link><Button variant="outline" size="icon" aria-label="Refresh subpanel definitions" title="Refresh subpanel definitions" onClick={onRefresh}><RefreshCw /></Button></div>}
    <fieldset disabled={readonly || pending} className="space-y-3"><legend className="type-title mb-3">Interpretation scopes</legend>
      <label className="flex items-center gap-2"><input type="checkbox" checked disabled />Base</label>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{context.subpanels.filter((scope) => scope.subpanel_id !== "base" && (scope.is_active || scopes.includes(scope.subpanel_id))).map((scope) => <label key={scope.subpanel_id} className="flex items-center gap-2"><input type="checkbox" checked={scopes.includes(scope.subpanel_id)} onChange={() => setScopes(toggle(scopes, scope.subpanel_id))} />{scope.display_name}{!scope.is_active && " (retired)"}</label>)}</div>
    </fieldset>
    <fieldset disabled={readonly || pending} className="space-y-3"><legend className="type-title mb-3">Environments to activate</legend><div className="flex flex-wrap gap-4">{context.environments.map((env) => <label key={env} className="flex items-center gap-2"><input type="checkbox" checked={environments.includes(env)} onChange={() => setEnvironments(toggle(environments, env))} />{env}</label>)}</div></fieldset>
    {!readonly && <Button disabled={pending} onClick={() => onSave({ ...content, scopes, environments })}><Save />Save scopes</Button>}
  </section>
}

export function AssaySetupPage() {
  const access = useCurrentUserAccess()
  const user = access.data
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const selected = params.get("setup") || (location.pathname === "/admin/asp/create" ? "new" : "")
  const isNew = selected === "new"
  const [step, setStep] = useState(0)
  const [editing, setEditing] = useState<number | null>(null)
  const [reason, setReason] = useState("")
  const client = useQueryClient()
  const canView = hasPermission(user, "assay.panel:view") && hasPermission(user, "assay.panel:list")
  const canWrite = writePermissions.every((permission) => hasPermission(user, permission))
  const list = useQuery({ queryKey: ["assay-setups"], enabled: canView, queryFn: () => api.get<{ items: Setup[] }>("/admin/assay-setups").then((r) => r.data.items) })
  const context = useQuery({ queryKey: ["assay-setup-context", selected], enabled: canView && Boolean(selected) && (!isNew || canWrite), queryFn: () => api.get<Context>(`/admin/assay-setups/${isNew ? "context" : `${encodeURIComponent(selected)}/context`}`).then((r) => r.data) })
  const setup = context.data?.setup
  const content = setup?.content
  const readonly = !canWrite || (setup != null && setup.status !== "draft")
  const mutation = useMutation({
    mutationFn: ({ content: next, action }: { content?: Content; action?: string }) => action
      ? api.post<Setup>(`/admin/assay-setups/${selected}/${action}`, { revision: setup?.revision, reason })
      : isNew ? api.post<Setup>("/admin/assay-setups", next) : api.put<Setup>(`/admin/assay-setups/${selected}`, { revision: setup?.revision, content: next }),
    onSuccess: async (response, variables) => {
      setParams({ setup: response.data._id })
      setEditing(null)
      setReason("")
      if (isNew) setStep(1)
      await client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      await client.invalidateQueries({ queryKey: ["assay-setups"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      if (variables.action === "publish") {
        void client.invalidateQueries({ queryKey: ["admin-resource"] })
        void client.invalidateQueries({ queryKey: ["subpanel-assay-options"] })
      }
      notifySuccess(variables.action === "publish" ? "Assay activated" : variables.action === "submit" ? "Setup submitted for review" : "Setup draft saved")
    },
    onError: (error) => notifyActionError("Assay setup", error),
  })
  const choose = (identifier: string) => { navigate(`/admin/assay-setups${identifier ? `?setup=${encodeURIComponent(identifier)}` : ""}`); setStep(0); setEditing(null); setReason(""); mutation.reset() }
  const save = (next: Content) => mutation.mutate({ content: next })
  const records = step === 2 ? content?.gene_lists || [] : content?.configurations || []
  const form = step === 2 ? context.data?.genelist_form : context.data?.configuration_form
  const field = step === 2 ? "gene_lists" : "configurations"
  const kind = step === 2 ? "genelists" : "aspc"
  const reviewAllowed = hasPermission(user, "assay.panel:edit") && setup?.status === "submitted" && !setup.content_editors.includes(user?.username || "")

  return <PageShell eyebrow="Admin" title="Assay setup" actions={canWrite ? <Button disabled={mutation.isPending} onClick={() => choose("new")}><Plus />New assay setup</Button> : undefined}>
    {access.isLoading ? <AppLoader label="Loading access" /> : !canView ? <p role="alert">Assay list and view permissions are required.</p> : <>
      <section className="surface-panel flex flex-wrap items-end gap-3 p-4">
        <label className="type-label min-w-0 flex-1">Saved setups<select aria-label="Saved setups" className="paper-inset mt-1 w-full rounded-md p-2" value={selected} disabled={mutation.isPending} onChange={(event) => choose(event.target.value)}><option value="">Select a setup</option>{isNew && <option value="new">New assay</option>}{(list.data || []).map((item) => <option key={item._id} value={item._id}>{item.asp_id} · {item.status} · r{item.revision}</option>)}</select></label>
        {setup && <span className="type-body font-semibold">{setup.status} · Revision {setup.revision}</span>}
      </section>
      {(list.error || context.error) && <p role="alert" className="text-destructive">Unable to load assay setup.</p>}
      {context.isLoading && <AppLoader label="Loading setup" />}
      {context.data && <>
        <nav aria-label="Assay setup steps" className="glass-card grid grid-cols-2 gap-2 p-3 md:grid-cols-3 xl:grid-cols-6">{steps.map(({ name, icon: Icon }, index) => <Button key={name} variant={step === index ? "default" : "outline"} className="h-auto justify-start whitespace-normal py-3" aria-current={step === index ? "step" : undefined} disabled={mutation.isPending || (isNew && index !== 0)} onClick={() => { setStep(index); setEditing(null) }}><Icon className="shrink-0" /><span>{index + 1}. {name}</span></Button>)}</nav>
        {mutation.error && <p role="alert" className="text-destructive">{mutation.error.message}</p>}
        {context.data.context_error && <p role="alert" className="text-destructive">{context.data.context_error}</p>}
        {step === 0 && <ResourceEditor key={`${selected}-${setup?.revision}`} kind="asp" form={{ ...context.data.panel_form, fields: { ...context.data.panel_form.fields, is_active: { ...context.data.panel_form.fields.is_active, hidden_mode: ["create", "view"] }, ...(setup ? { asp_id: { ...context.data.panel_form.fields.asp_id, readonly: true } } : {}) } }} source={content?.panel || {}} readonly={readonly} pending={mutation.isPending} onCancel={() => choose("")} onSave={(panel) => save(content ? { ...content, panel: { ...panel, asp_id: content.panel.asp_id } } : emptyContent(panel))} />}
        {step === 1 && content && <ScopeEditor key={`${selected}-${setup?.revision}`} content={content} context={context.data} readonly={readonly} pending={mutation.isPending} onSave={save} onRefresh={() => void context.refetch()} />}
        {(step === 2 || step === 4) && content && <>
          <div className="flex items-center justify-between gap-3"><h2 className="type-title">{step === 2 ? "Staged gene lists" : "Scope configurations"}</h2>{!readonly && <Button variant="outline" disabled={!form || mutation.isPending} onClick={() => setEditing(records.length)}><Plus />{step === 2 ? "Add gene list" : "Add configuration"}</Button>}</div>
          {step === 4 && <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-muted"><tr><th className="p-3">Scope</th><th className="p-3">Environment</th><th className="p-3">Configuration</th></tr></thead><tbody>{content.scopes.flatMap((scope) => content.environments.map((env) => <tr key={`${scope}-${env}`} className="border-b border-border"><td className="p-3">{scope}</td><td className="p-3">{env}</td><td className="p-3">{records.some((r) => (r.subpanel_id || "base") === scope && r.environment === env) ? "Configured" : "Missing"}</td></tr>))}</tbody></table></div>}
          <ul className="divide-y divide-border">{records.map((record, index) => <li key={index} className="flex flex-wrap items-center justify-between gap-2 py-3"><span className="min-w-0 break-words type-body">{String(record.displayname || record.display_name || record.name || record.isgl_id || `Configuration ${index + 1}`)}{step === 4 && ` · ${record.subpanel_id || "base"} / ${record.environment || ""}`}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={!form} onClick={() => setEditing(index)}><Edit />{readonly ? "View" : "Edit"}</Button>{!readonly && <Button variant="ghost" size="icon" aria-label={`Remove ${step === 2 ? "gene list" : "configuration"} ${index + 1}`} disabled={mutation.isPending} onClick={() => save({ ...content, [field]: records.filter((_, i) => i !== index) })}><Trash2 /></Button>}</div></li>)}</ul>
          {!records.length && <p className="type-body text-muted-foreground">{step === 2 ? "No staged gene lists. Gene lists are optional unless required by the selected filters." : "No configurations saved."}</p>}
          {editing != null && form && <ResourceEditor key={`${selected}-${setup?.revision}-${step}-${editing}`} kind={kind} form={form} source={records[editing] || (step === 2 ? { asp_ids: [setup?.asp_id], asp_groups: [content.panel.asp_group], diagnosis: ["base"] } : { asp_id: setup?.asp_id, asp_group: content.panel.asp_group, asp_category: content.panel.asp_category, display_name: content.panel.display_name, platform: content.panel.platform, subpanel_id: "base", environment: content.environments[0] })} readonly={readonly} pending={mutation.isPending} onCancel={() => setEditing(null)} onSave={(record) => { const next = [...records]; next[editing] = record; save({ ...content, [field]: next }) }} />}
        </>}
        {step === 3 && content && <section className="surface-panel space-y-4 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="type-title">Published reporting rules</h2><div className="flex gap-2"><Link className="inline-flex items-center gap-2 text-primary underline" to="/admin/clinical-rules" target="_blank" rel="noopener noreferrer"><FileCheck className="size-4" />Open rule builder</Link><Button variant="outline" size="icon" aria-label="Refresh reporting rules" title="Refresh reporting rules" onClick={() => void context.refetch()}><RefreshCw /></Button></div></div>
          <ul className="divide-y divide-border">{(context.data.rules || []).map((rule) => <li key={rule._id} className="flex flex-wrap items-center gap-2 py-3"><Check className="size-4 text-pass" /><span className="type-body">{rule.scope.subpanel_id} · {rule.name} · v{rule.content_version}</span></li>)}</ul>
          {!context.data.rules?.length && <p role="status">No published reporting rules for this assay.</p>}
        </section>}
        {step === 5 && setup && <section className="surface-panel space-y-4 p-4"><h2 className="type-title">Review and activation</h2><dl className="grid gap-3 sm:grid-cols-2"><div><dt className="type-label">Assay</dt><dd>{String(setup.content.panel.display_name)} ({setup.asp_id})</dd></div><div><dt className="type-label">Scopes</dt><dd>{setup.content.scopes.join(", ")}</dd></div><div><dt className="type-label">Environments</dt><dd>{setup.content.environments.join(", ") || "None selected"}</dd></div><div><dt className="type-label">Created by</dt><dd>{setup.created_by}</dd></div></dl>
          {setup.status !== "published" && <div role="status" className={cn("rounded-md border p-3", context.data.readiness?.ready ? "border-pass text-pass" : "border-warning")}>
            {context.data.readiness?.ready ? "Ready for independent review" : <ul>{context.data.readiness?.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
          </div>}
          {setup.review_reason && <p className="type-body">Review: {setup.review_reason}</p>}
          {setup.status === "draft" && canWrite && <Button disabled={!context.data.readiness?.ready || mutation.isPending} onClick={() => mutation.mutate({ action: "submit" })}><ClipboardCheck />Submit for review</Button>}
          {reviewAllowed && <><label className="type-label block">Review notes<textarea className="paper-inset mt-1 min-h-24 w-full rounded-md p-3" value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="flex flex-wrap gap-3">{canWrite && <Button disabled={!context.data.readiness?.ready || mutation.isPending} onClick={() => mutation.mutate({ action: "publish" })}><Check />Approve and activate</Button>}<Button variant="outline" disabled={!reason.trim() || mutation.isPending} onClick={() => mutation.mutate({ action: "return" })}><ArrowLeft />Return for changes</Button></div></>}
          {setup.status === "submitted" && !reviewAllowed && <p role="status">Awaiting independent review.</p>}
          {setup.status === "published" && <p role="status">Assay setup published. Manage subsequent changes from the individual resource pages.</p>}
          <details><summary className="cursor-pointer type-label">Revision history</summary><ul className="mt-3 divide-y divide-border">{context.data.history?.map((entry) => <li key={entry.revision} className="py-2 type-body">r{entry.revision} · {entry.action} · {entry.actor} · {new Date(entry.at).toLocaleString()}</li>)}</ul></details>
        </section>}
        {!isNew && <footer className="flex items-center justify-between"><Button variant="outline" disabled={step === 0 || mutation.isPending} onClick={() => { setStep(step - 1); setEditing(null) }}><ArrowLeft />Previous</Button><span className="type-meta text-muted-foreground">Step {step + 1} of {steps.length}</span><Button variant="outline" disabled={step === steps.length - 1 || mutation.isPending} onClick={() => { setStep(step + 1); setEditing(null) }}>Next<ArrowRight /></Button></footer>}
      </>}
    </>}
  </PageShell>
}
