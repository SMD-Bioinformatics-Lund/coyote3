import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Link } from "react-router-dom"
import { PageShell } from "@/components/layout/PageShell"
import { DataTable } from "@/components/data-table/DataTable"
import { JsonDocumentEditor } from "@/components/admin/JsonDocumentEditor"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { StatusBadge } from "./resource-list"

type Section = "profiles" | "promotions"
type Entry = Record<string, unknown> & {
  _id: string; name?: string; profile_id?: string; kind?: string; version?: number;
  status: string; content_hash: string; created_by: string;
  candidate?: Record<string, unknown>;
}
const initialProfile = {
  profile_id: "", name: "", kind: "filters", bindings: [{ environment: "testing" }],
  content: { somatic: { snv: { min_depth: 100 } } }, reason: "",
}
const initialPromotion = { source_id: "", target_environment: "validation", evidence: [""], reason: "" }

export function ConfigurationProfilesPage() {
  const access = useCurrentUserAccess()
  const client = useQueryClient()
  const allowed = hasPermission(access.data, "assay.config:list")
  const canCreate = hasPermission(access.data, "assay.config:create")
  const canPublish = hasPermission(access.data, "configuration:publish")
  const [section, setSection] = useState<Section>("profiles")
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)
  const [review, setReview] = useState<Entry | null>(null)
  const [reason, setReason] = useState("")
  const path = `/resources/configuration-${section}`
  const rows = useQuery({
    queryKey: ["configuration-governance", section], enabled: allowed,
    queryFn: () => api.get<Entry[]>(path).then((response) => response.data),
  })
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ["configuration-governance"] })
    void client.invalidateQueries({ queryKey: ["admin-resource-list"] })
  }
  const create = useMutation({
    mutationFn: (document: Record<string, unknown>) => api.post(path, document),
    onSuccess: () => { setDraft(null); invalidate(); notifySuccess("Draft saved for independent review") },
    onError: (error) => notifyActionError("Save configuration draft", error),
  })
  const publish = useMutation({
    mutationFn: () => api.post(`${path}/${review!._id}/${section === "profiles" ? "publish" : "approve"}`, {
      content_hash: review!.content_hash, reason: reason.trim(),
    }),
    onSuccess: () => { setReview(null); setReason(""); invalidate(); notifySuccess("Configuration approval recorded") },
    onError: (error) => notifyActionError("Approve configuration", error),
  })
  const columns: ColumnDef<Entry>[] = [
    { header: "Name", accessorFn: (row) => row.name || String(row.candidate?.aspc_id || "Promotion") },
    { header: "Component", accessorFn: (row) => row.kind || String(row.candidate?.environment || "") },
    { header: "Revision", accessorFn: (row) => row.version || row.candidate?.version || "" },
    { header: "Status", accessorKey: "status", cell: ({ row }) => <StatusBadge value={row.original.status} /> },
    { header: "Author", accessorKey: "created_by" },
    { id: "actions", header: "Actions", cell: ({ row }) => <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={() => { setReview(row.original); setDraft(null); setReason("") }}>Review</Button>
      {canCreate && section === "profiles" && <Button variant="ghost" size="sm" onClick={() => {
        const item = row.original
        setReview(null)
        setDraft({ profile_id: item.profile_id, name: item.name, kind: item.kind, bindings: item.bindings, content: item.content, reason: "" })
      }}>New revision</Button>}
    </div> },
  ]
  return <PageShell eyebrow="Admin" title="Configuration governance"
    description="Reusable profiles and reviewed environment promotions. Existing samples retain their applied releases."
    actions={<Link to="/admin/aspc" className="text-primary underline">Assay configurations</Link>}>
    <div className="glass-card space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        {(["profiles", "promotions"] as const).map((value) => <Button key={value}
          variant={section === value ? "default" : "outline"} aria-pressed={section === value}
          onClick={() => { setSection(value); setDraft(null); setReview(null) }}>
          {value === "profiles" ? "Reusable profiles" : "Environment promotions"}
        </Button>)}
        {canCreate && <Button variant="outline" onClick={() => {
          setReview(null); setDraft(section === "profiles" ? initialProfile : initialPromotion)
        }}>{section === "profiles" ? "Create profile" : "Propose promotion"}</Button>}
      </div>
      {rows.isError ? <p role="alert">Configuration records could not be loaded. <Button variant="link" onClick={() => void rows.refetch()}>Retry</Button></p>
        : rows.isPending ? <p role="status">Loading configuration records…</p>
        : <DataTable columns={columns} data={rows.data || []} filename={`configuration-${section}.csv`} />}
      {draft && <JsonDocumentEditor document={draft} onCancel={() => setDraft(null)}
        onSave={(value) => create.mutate(value)} isSaving={create.isPending} />}
      {review && <section className="space-y-3" aria-label="Configuration review">
        <JsonDocumentEditor document={review} readOnly onCancel={() => setReview(null)} onSave={() => undefined} />
        {canPublish && ["draft", "pending"].includes(review.status) && review.created_by !== access.data?.username && <>
          <label htmlFor="configuration-review-reason" className="type-body">Review decision</label>
          <Input id="configuration-review-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Record the validation and review decision" />
          <Button disabled={reason.trim().length < 3 || publish.isPending} onClick={() => publish.mutate()}>
            {section === "profiles" ? "Publish reviewed profile" : "Approve environment promotion"}
          </Button>
        </>}
        {review.created_by === access.data?.username && ["draft", "pending"].includes(review.status) &&
          <p className="type-body text-muted-foreground">Another authorized user must approve this draft.</p>}
      </section>}
    </div>
  </PageShell>
}
