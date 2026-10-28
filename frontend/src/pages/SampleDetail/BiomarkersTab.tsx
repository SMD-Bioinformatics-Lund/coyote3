import { SurfacePanel } from "@/components/cards/Panel"
import { AppLoader } from "@/components/layout/AppLoader"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

type AssessmentValue = "HIGH" | "MODERATE" | "LOW"
type Assessment = { value: AssessmentValue | null; revision: number; assessed_by: string; assessed_at: string }
type Measurement = {
  clinical_assessment?: Assessment | null
  sum?: number; tai?: number; hrd?: number; lst?: number
  per?: number; som?: number; tot?: number; value?: number; unit?: string
}
type BiomarkerRecord = { _id: string; name: string } & Partial<Record<"HRD" | "MSIS" | "MSIP" | "TMB", Measurement>>
type Payload = { biomarkers: BiomarkerRecord[]; analysis_types: string[] }
const methods = ["HRD", "MSIS", "MSIP", "TMB"] as const
const options = [
  { value: "", label: "Not assessed" },
  { value: "HIGH", label: "High" },
  { value: "MODERATE", label: "Moderate" },
  { value: "LOW", label: "Low" },
]

function measuredValue(method: string, measurement: Measurement): string {
  if (method === "HRD") return `${measurement.sum ?? "-"} (TAI: ${measurement.tai ?? "-"}; HRD: ${measurement.hrd ?? "-"}; LST: ${measurement.lst ?? "-"})`
  if (method === "TMB") return `${measurement.value ?? "-"} ${measurement.unit || "mut/Mb"}`
  return `${measurement.per ?? "-"}% (${measurement.som ?? "-"}/${measurement.tot ?? "-"})`
}

function AssessmentEditor({ recordId, method, measurement, sampleId, canEdit }: {
  recordId: string; method: string; measurement: Measurement; sampleId: string; canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState<string>(measurement.clinical_assessment?.value || "")
  const [revision, setRevision] = useState(measurement.clinical_assessment?.revision || 0)
  const [editing, setEditing] = useState(false)
  const editor = useDocumentEditor("sample-biomarkers", sampleId, canEdit && editing)
  const mutation = useMutation({
    mutationFn: () => api.patch<Payload>(
      `/samples/${encodeURIComponent(sampleId)}/biomarkers/${encodeURIComponent(recordId)}/assessments/${method}`,
      { value: value || null, expected_revision: revision },
      editor.options(),
    ),
    onSuccess: ({ data }) => {
      queryClient.setQueryData(["sample-biomarkers", sampleId], data)
      void queryClient.invalidateQueries({ queryKey: ["report-preview"] })
      setEditing(false)
    },
  })
  return <div className="space-y-2">
    {editing ? <>
      <Select label={`${method} clinical assessment`} value={value} options={options}
        disabled={!editor.owned || mutation.isPending} onValueChange={setValue} />
      <div className="flex gap-2">
        <Button size="sm" disabled={!editor.owned || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Saving…" : "Save assessment"}
        </Button>
        <Button size="sm" variant="outline" disabled={mutation.isPending} onClick={() => setEditing(false)}>Cancel</Button>
      </div>
      {editor.pending && <p className="type-meta text-muted-foreground">Starting editing session…</p>}
      {editor.owner && !editor.owned && <p role="status" className="type-body-sm text-muted-foreground">Being edited by {editor.owner}.</p>}
      {(mutation.error || editor.error) && <p role="alert" className="type-body-sm text-destructive">{mutation.error instanceof Error ? mutation.error.message : editor.error}</p>}
    </> : <div className="flex flex-wrap items-center gap-3">
      <span className="type-body font-semibold">{measurement.clinical_assessment?.value || "Not assessed"}</span>
      {canEdit && <Button size="sm" variant="outline" onClick={() => {
        setValue(measurement.clinical_assessment?.value || "")
        setRevision(measurement.clinical_assessment?.revision || 0)
        mutation.reset()
        setEditing(true)
      }}>Edit {method} assessment</Button>}
    </div>}
    {measurement.clinical_assessment && <p className="type-meta text-muted-foreground">
      Saved by {measurement.clinical_assessment.assessed_by} · {new Date(measurement.clinical_assessment.assessed_at).toLocaleString()}
    </p>}
  </div>
}

export function BiomarkersTab({ sampleId, production }: { sampleId: string; production: boolean }) {
  const access = useCurrentUserAccess()
  const canEdit = hasPermission(access.data, "sample:edit:own")
    && (!production || hasPermission(access.data, "annotation:publish"))
  const query = useQuery({
    queryKey: ["sample-biomarkers", sampleId],
    queryFn: () => api.get<Payload>(`/samples/${encodeURIComponent(sampleId)}/biomarkers`).then(({ data }) => data),
    retry: false,
  })
  if (query.isLoading) return <AppLoader />
  if (query.error) return <p role="alert" className="text-destructive type-body">{query.error.message}</p>
  return <SurfacePanel title="Biomarker analysis" description="Review measured results and assign a clinical assessment. Assessments are saved separately from the scores and are used in the report summary. No assessment is calculated automatically.">
    {!query.data?.biomarkers.length && <p className="type-body text-muted-foreground">No measured biomarkers are available for the enabled analyses.</p>}
    <div className="grid gap-4 lg:grid-cols-2">
      {query.data?.biomarkers.flatMap(record => methods.map(method => {
        const measurement = record[method]
        if (!measurement) return null
        return <section key={`${record._id}-${method}`} className="surface-panel space-y-3 p-4">
          <h3 className="type-card-title">{method} · {record.name}</h3>
          <p className="type-body"><span className="text-muted-foreground">Measured result: </span>{measuredValue(method, measurement)}</p>
          <AssessmentEditor recordId={record._id} method={method} measurement={measurement} sampleId={sampleId} canEdit={canEdit} />
        </section>
      }))}
    </div>
  </SurfacePanel>
}
