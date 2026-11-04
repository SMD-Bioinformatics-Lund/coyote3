import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link } from "react-router-dom"
import { Select } from "@/components/ui/select"
import { api } from "@/lib/api"
import { buttonVariants } from "@/components/ui/button-variants"

type SetupSummary = { _id: string; asp_id: string; status: string }
type SetupContext = { setup: { status: string; revision: number; content: {
  panel: Record<string, unknown>; configurations: Record<string, unknown>[]
} } }

export function CopySetupConfiguration() {
  const [selected, setSelected] = useState("")
  const [configuration, setConfiguration] = useState("")
  const list = useQuery({ queryKey: ["assay-setups"], queryFn: () => api.get<{ items: SetupSummary[] }>("/admin/assay-setups").then(result => result.data.items) })
  const context = useQuery({ queryKey: ["assay-setup-context", selected], enabled: Boolean(selected), queryFn: () => api.get<SetupContext>(`/admin/assay-setups/${encodeURIComponent(selected)}/context`).then(result => result.data) })
  const drafts = (list.data || []).filter(setup => setup.status === "draft")
  const content = context.data?.setup.status === "draft" ? context.data.setup.content : undefined
  const choices = (content?.configurations || []).map((record, index) => ({
    value: `${context.data?.setup.revision}:${index}`, record,
    label: `${String(record.display_name || record.aspc_id || "Configuration")} · ${String(record.diagnosis_id || "base")} / ${String(record.environment || "")}`,
  }))
  const source = choices.find(choice => choice.value === configuration)?.record
  return <section aria-label="Copy configuration from setup draft" className="surface-panel space-y-3 p-4">
    <h2 className="type-title">Copy from setup draft</h2>
    <p className="type-body-sm text-muted-foreground">Open a staged configuration in the create form. Choose its target assay, diagnosis and environment before saving. The target assay must be activated; the source draft stays unchanged.</p>
    {list.isPending ? <p role="status">Loading setup drafts…</p> : list.isError ? <p role="alert">Could not load setup drafts. <button className="text-primary underline" onClick={() => void list.refetch()}>Retry drafts</button></p> : !drafts.length ? <p className="type-body-sm text-muted-foreground">No setup drafts available.</p> : <Select label="Source setup draft" value={selected} options={[{ value: "", label: "Choose a setup draft" }, ...drafts.map(setup => ({ value: setup._id, label: setup.asp_id }))]} onValueChange={value => { setSelected(value); setConfiguration("") }} />}
    {selected && (context.isPending ? <p role="status">Loading staged configurations…</p> : context.isError ? <p role="alert">Could not load staged configurations. <button className="text-primary underline" onClick={() => void context.refetch()}>Retry configurations</button></p> : !content?.configurations.length ? <p className="type-body-sm text-muted-foreground">This draft has no staged configurations available to copy.</p> : <Select label="Source staged configuration" value={source ? configuration : ""} disabled={context.isFetching} options={[{ value: "", label: "Choose a configuration" }, ...choices]} onValueChange={setConfiguration} />)}
    {configuration && !source && !context.isError && <p role="status" className="type-body-sm text-muted-foreground">The source draft changed. Choose a configuration again.</p>}
    {source && content && !context.isFetching && !context.isError && <Link className={buttonVariants({ variant: "outline", className: "whitespace-normal" })} to="/admin/aspc/create" state={{ copiedDocument: { ...source, asp_id: content.panel.asp_id, asp_category: source.asp_category || content.panel.asp_category } }}>Copy staged configuration as new</Link>}
  </section>
}
