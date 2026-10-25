import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { api } from "@/lib/api"

export type ConfigurationApplication = {
  expected_version: number
  configuration_id: string
  reason: string
  retain_overrides: boolean
}

type Preview = {
  expected_version: number
  configuration_id: string
  configuration: { aspc_id: string; version: number; analysis_types: string[] }
  filters_before: Record<string, Record<string, Record<string, unknown>>>
  filters_after: Record<string, Record<string, Record<string, unknown>>>
  changed_components: string[]
}

export function ConfigurationApplyButton({ sampleId, pending, apply }: {
  sampleId: string
  pending: boolean
  apply: (request: ConfigurationApplication) => Promise<unknown>
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [retain, setRetain] = useState(false)
  const preview = useQuery({
    queryKey: ["sample-configuration-preview", sampleId, retain],
    queryFn: () => api.get<Preview>(`/samples/${sampleId}/aspc/preview?retain_overrides=${retain}`).then(response => response.data),
    enabled: open,
    staleTime: 0,
  })
  const changes = Object.entries(preview.data?.filters_after ?? {}).flatMap(([intent, targets]) =>
    Object.entries(targets).flatMap(([target, fields]) => Object.entries(fields).flatMap(([key, after]) => {
      const before = preview.data?.filters_before?.[intent]?.[target]?.[key]
      return JSON.stringify(before) === JSON.stringify(after) ? [] : [{
        name: `${intent} / ${target} / ${key}`,
        before: JSON.stringify(before) ?? "Unset",
        after: JSON.stringify(after),
      }]
    })),
  )
  return <>
    <button type="button" className="btn-primary mt-2" onClick={() => setOpen(true)}>
      Review configuration update
    </button>
    <ConfirmationDialog open={open} title="Apply assay configuration" confirmLabel="Apply configuration"
      isPending={pending} confirmDisabled={!preview.data || preview.isFetching || preview.isError || !reason.trim()}
      onCancel={() => setOpen(false)} onConfirm={async () => {
        if (!preview.data) return
        await apply({ expected_version: preview.data.expected_version,
          configuration_id: preview.data.configuration_id, reason: reason.trim(), retain_overrides: retain })
        setOpen(false)
        setReason("")
      }} description={<div className="space-y-3">
        <p>Review assay settings and filter defaults. Query and reporting rules resolve independently from published scopes. Saved reports retain their original configuration and rules.</p>
        <label className="flex items-center gap-2"><input type="checkbox" checked={retain}
          disabled={pending} onChange={event => setRetain(event.target.checked)} />Retain compatible sample overrides</label>
        {preview.isFetching && <p role="status">Preparing configuration preview…</p>}
        {preview.isError && <p role="alert">The configuration could not be resolved. Refresh the sample and try again.</p>}
        {preview.data && <>
          <p>{preview.data.configuration.aspc_id} · revision {preview.data.configuration.version}</p>
          <p>Analyses: {preview.data.configuration.analysis_types.join(", ")}</p>
          <p>Changed resources: {preview.data.changed_components.map(key => ({
            assay_resource_release: "assay eligibility", gene_list_release: "gene lists",
          }[key] ?? key)).join(", ") || "None"}</p>
          <div className="max-h-64 overflow-auto">
            {changes.length ? changes.map(change => <div key={change.name} className="border-b border-border py-2">
              <strong>{change.name}</strong><p className="break-all">{change.before} → {change.after}</p>
            </div>) : <p>No filter values change.</p>}
          </div>
        </>}
        <label className="block">Reason for applying this release
          <textarea className="mt-1 w-full rounded border border-border bg-background p-2 text-foreground"
            value={reason} maxLength={2000} disabled={pending} onChange={event => setReason(event.target.value)} />
        </label>
      </div>} />
  </>
}
