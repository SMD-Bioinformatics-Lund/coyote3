// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { api } from "@/lib/api"

export type ConfigurationApplication = {
  expected_version: number
  configuration_id: string
  reason: string
  retain_overrides: boolean
  accept_incompatible_overrides?: boolean
}

type Filters = Record<string, Record<string, Record<string, unknown> | null> | null> | null

function filterFields(filters: Filters | undefined) {
  return Object.fromEntries(Object.entries(filters ?? {}).flatMap(([intent, targets]) =>
    Object.entries(targets ?? {}).flatMap(([target, fields]) => Object.entries(fields ?? {})
      .map(([field, value]) => [`${intent} / ${target} / ${field}`, JSON.stringify(value)]))))
}

type Preview = {
  expected_version: number
  configuration_id: string
  configuration: { aspc_id: string; version: number; analysis_types: string[] }
  incompatible_overrides: string[]
  previous_configuration: {aspc_id: string; version: number} | null
  gene_list_changes: {isgl_id: string; previous_version: number | null; version: number | null; added_genes: string[]; removed_genes: string[]}[]
  filters_before: Filters
  filters_after: Filters
  changed_components: string[]
}

export function ConfigurationApplyButton({ sampleId, pending, apply }: {
  sampleId: string
  pending: boolean
  apply: (request: ConfigurationApplication) => Promise<unknown>
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [retain, setRetain] = useState(true)
  const [accepted, setAccepted] = useState(false)
  const preview = useQuery({
    queryKey: ["sample-configuration-preview", sampleId, retain],
    queryFn: () => api.get<Preview>(`/samples/${sampleId}/aspc/preview?retain_overrides=${retain}`).then(response => response.data),
    enabled: open,
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const before = filterFields(preview.data?.filters_before)
  const after = filterFields(preview.data?.filters_after)
  const changes = [...new Set([...Object.keys(before), ...Object.keys(after)])]
    .filter(key => before[key] !== after[key])
  return <>
    <button type="button" className="btn-primary mt-2" onClick={() => { setReason(""); setAccepted(false); setRetain(true); setOpen(true) }}>
      Review configuration update
    </button>
    <ConfirmationDialog open={open} title="Apply assay configuration" confirmLabel="Apply configuration"
      isPending={pending} confirmDisabled={!preview.data || preview.isFetching || preview.isError || !reason.trim() || (Boolean(preview.data?.incompatible_overrides?.length) && !accepted)}
      onCancel={() => setOpen(false)} onConfirm={async () => {
        if (!preview.data) return
        try {
          await apply({ expected_version: preview.data.expected_version,
            configuration_id: preview.data.configuration_id, reason: reason.trim(), retain_overrides: retain, ...(preview.data.incompatible_overrides?.length ? {accept_incompatible_overrides: accepted} : {}) })
        } catch {
          setAccepted(false)
          await preview.refetch()
          return
        }
        setOpen(false)
        setReason("")
      }} description={<div className="space-y-3">
        <p>This update applies to this sample. Saved reports retain their original settings.</p>
        <label className="flex items-center gap-2"><input type="checkbox" checked={retain}
          disabled={pending} onChange={event => { setRetain(event.target.checked); setAccepted(false) }} />Retain compatible sample overrides</label>
        {preview.isFetching && <p role="status">Preparing configuration preview…</p>}
        {preview.isError && <p role="alert">{preview.error.message}</p>}
        {preview.data && <>
          <p>{preview.data.previous_configuration ? `${preview.data.previous_configuration.aspc_id} v${preview.data.previous_configuration.version}` : "No pinned configuration"} → {preview.data.configuration.aspc_id} v{preview.data.configuration.version}</p>
          {preview.data.gene_list_changes?.filter(list => list.added_genes?.length || list.removed_genes?.length).map(list => <div key={list.isgl_id}>
            <strong>{list.isgl_id}</strong> · {list.previous_version == null ? "New" : `v${list.previous_version}`} → {list.version == null ? "Removed" : `v${list.version}`}
            {Boolean(list.added_genes?.length) && <p>Added genes: {list.added_genes?.join(", ")}</p>}
            {Boolean(list.removed_genes?.length) && <p>Removed genes: {list.removed_genes?.join(", ")}</p>}
          </div>)}
          {Boolean(preview.data.incompatible_overrides?.length) && <div role="group" className="space-y-2">
            <p>These sample overrides are unavailable in the proposed revision.</p>
            <ul>{preview.data.incompatible_overrides.map(value => <li key={value}>{value}</li>)}</ul>
            <label><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} /> Apply the changes shown above</label>
          </div>}
          <p>Analyses: {preview.data.configuration.analysis_types.join(", ")}</p>
          {preview.data.changed_components.includes("assay_resource_release") && <p>The assay definition has changed.</p>}
          <div className="max-h-64 overflow-auto">
            {changes.length ? changes.map(change => <div key={change} className="border-b border-border py-2">
              <strong>{change}</strong><p className="break-all">{before[change] ?? "Unset"} → {after[change] ?? "Unset"}</p>
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
