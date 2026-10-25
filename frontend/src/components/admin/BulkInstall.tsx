import { useId, useMemo, useRef, useState } from "react"
import { Dialog } from "@base-ui/react/dialog"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { api, ApiClientError } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { downloadJson } from "@/lib/json-download"
import { formStateFromSpec, submitPayload } from "@/pages/admin/resource-list"
import type { FormSpec } from "@/pages/admin/resource-specs"
import { BULK_BYTES, bulkDefinitions, parseBulkFile, type BulkKind, type BulkRecord } from "./bulk-import"

type Result = { row: number; identity: string; status: string }

/** Preview and create independent records through their permission-checked resource APIs. */
export function BulkInstall({ kind }: { kind: BulkKind }) {
  const access = useCurrentUserAccess()
  const definition = bulkDefinitions[kind]
  const allowed = hasPermission(access.data, definition.permission)
  const client = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<"example" | "paste" | "preview" | null>(null)
  const [draft, setDraft] = useState("")
  const [format, setFormat] = useState<"json" | "yaml">("json")
  const [source, setSource] = useState<"file" | "paste">("file")
  const editorId = useId()
  const [category, setCategory] = useState("DNA")
  const [records, setRecords] = useState<BulkRecord[]>([])
  const [results, setResults] = useState<Result[]>([])
  const [error, setError] = useState("")
  const [running, setRunning] = useState(false)
  const [reading, setReading] = useState(false)
  const [attempted, setAttempted] = useState(false)
  const endpoint = `/resources/${kind}`
  const contract = useQuery({
    queryKey: ["bulk-install-contract", kind, category], enabled: allowed,
    queryFn: async () => {
      if ("example" in definition) return { example: definition.example as BulkRecord, required: [...definition.required] as string[], form: null }
      const { data } = await api.get<{ form: FormSpec }>(`${endpoint}/create_context${kind === "aspc" ? `?category=${category}` : ""}`)
      if (!data.form?.fields) throw new Error("The server did not provide the resource fields")
      const example = submitPayload(data.form, formStateFromSpec(data.form, {}), "create") as BulkRecord
      // Keep numeric keys in the example even when an empty form omits their value.
      for (const [key, field] of Object.entries(data.form.fields)) {
        if (!field.readonly && !field.readonly_mode?.includes("create") && !(key in example)) example[key] = field.default ?? null
      }
      const required = Object.entries(data.form.fields).filter(([key, field]) => key in example && field.required).map(([key]) => key)
      return { example, required, form: data.form }
    },
  })
  const validation = useMemo(() => {
    if (mode !== "paste" || !draft.trim() || !contract.data) return { records: [], error: "" }
    try {
      return { records: parseBulkFile(draft, `pasted.${format}`, Object.keys(contract.data.example), contract.data.required, definition.identity), error: "" }
    } catch (failure) {
      return { records: [], error: failure instanceof Error ? failure.message : "Invalid content" }
    }
  }, [mode, draft, format, contract.data, definition.identity])
  if (!allowed) return null
  const example = contract.data?.example ?? {}
  const keys = Object.keys(example)
  const install = async () => {
    if (running || attempted || !records.length) return
    setRunning(true)
    setAttempted(true)
    const completed: Result[] = []
    for (const [index, record] of records.entries()) {
      const identity = definition.identity.split(",").map((key) => String(record[key])).join(" / ")
      try {
        await api.post(endpoint, "example" in definition ? record : { config: record })
        completed.push({ row: index + 1, identity, status: "Created" })
      } catch (failure) {
        completed.push({ row: index + 1, identity, status: failure instanceof Error ? failure.message : "Creation failed" })
        // Stop when authentication is lost, access is denied, or the outcome is uncertain.
        if (!(failure instanceof ApiClientError) || !failure.status || failure.status === 401 || failure.status === 403 || failure.status >= 500 || failure.status === 429) {
          completed.push(...records.slice(index + 1).map((remaining, offset) => ({ row: index + offset + 2, identity: definition.identity.split(",").map((key) => String(remaining[key])).join(" / "), status: "Not attempted" })))
          break
        }
      }
      setResults([...completed])
    }
    setResults(completed)
    setRunning(false)
    await Promise.all([
      ["admin-resource"], ["admin-resource-context"], ["diagnosis-definitions"],
      ["diagnosis-all-assays"], ["diagnosis-assay-options"], ["assay-diagnoses"],
      ["assay-groups"], ["assay-setup-context"], ["clinical-rule-authoring-options"],
      ["admin-public-assay-catalog"], ["assay-catalog-nav"], ["public-catalog"],
      ["public-catalog-matrix"], ["bulk-install-contract"],
    ].map((queryKey) => client.invalidateQueries({ queryKey })))
  }
  return <div className="flex flex-wrap items-center gap-2">
    {kind === "aspc" && <label className="type-label">Bulk category <select aria-label="Bulk configuration category" className="paper-inset rounded p-2" value={category} disabled={running || reading} onChange={(event) => setCategory(event.target.value)}><option>DNA</option><option>RNA</option></select></label>}
    <input ref={input} type="file" accept=".json,.yaml,.yml" aria-label={`Bulk upload ${kind}`} className="sr-only" disabled={running || reading || !contract.data} onChange={async (event) => {
      const file = event.target.files?.[0]
      event.target.value = ""
      if (!file || !contract.data) return
      setError(""); setRecords([]); setResults([]); setAttempted(false); setReading(true)
      try {
        if (file.size > BULK_BYTES) throw new Error("File must be no larger than 1 MiB")
        setRecords(parseBulkFile(await file.text(), file.name, keys, contract.data.required, definition.identity))
        setSource("file")
        setMode("preview")
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to read file") }
      finally { setReading(false) }
    }} />
    <Button variant="outline" disabled={running || reading || !contract.data} onClick={() => input.current?.click()}>Upload JSON / YAML</Button>
    <Button variant="outline" disabled={running || reading || !contract.data} onClick={() => setMode("paste")}>Paste JSON / YAML</Button>
    <Button variant="outline" disabled={running || reading || !contract.data} onClick={() => setMode("example")}>Show example</Button>
    {contract.isLoading && <span role="status" className="type-meta">Loading accepted fields…</span>}
    {(error || contract.error) && <p role="alert" className="type-body-sm text-destructive">{error || contract.error?.message}</p>}
    <Dialog.Root open={mode !== null} onOpenChange={(open) => { if (!open && !running) setMode(null) }}>
      <Dialog.Portal><Dialog.Backdrop className="fixed inset-0 z-50 bg-background/80" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 max-h-[85dvh] w-[min(48rem,95vw)] -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-lg border border-border bg-card p-5 text-card-foreground shadow-lg">
          <Dialog.Title className="type-card-title">{mode === "example" ? "Bulk file example" : mode === "paste" ? "Paste bulk records" : "Review bulk installation"}</Dialog.Title>
          <Dialog.Description className="my-3 type-body-sm">Paste a small list or upload a file for larger structures: a JSON array or YAML list of 1–100 records, up to 1 MiB, for one resource type. Each record is created separately with your current permissions. Existing records are not overwritten; successful records remain if another fails.</Dialog.Description>
          {mode === "example" ? <>
            <p className="type-body-sm">Replace example values with your center's settings. Required keys: {contract.data?.required.join(", ") || "See field details"}. References must already exist; diagnoses may use an empty asp_ids list.</p>
            <pre className="paper-inset my-3 overflow-auto rounded p-3 type-body-sm">{JSON.stringify([example], null, 2)}</pre>
            <p className="type-body-sm">Accepted top-level keys: {keys.join(", ")}. Authorship, timestamps and system ownership are assigned by the server.</p>
            {contract.data?.form && <details className="my-3"><summary className="cursor-pointer">Field types, nested fields and choices</summary><pre className="overflow-auto type-body-sm">{JSON.stringify(Object.fromEntries(Object.entries(contract.data.form.fields).filter(([key]) => keys.includes(key))), null, 2)}</pre></details>}
            <Button variant="outline" onClick={() => downloadJson(`${kind}-bulk-example`, [example])}>Download example JSON</Button>
            <Button variant="outline" onClick={() => { setDraft(JSON.stringify([example], null, 2)); setFormat("json"); setMode("paste") }}>Edit example</Button>
          </> : mode === "paste" ? <div className="space-y-3">
            <label className="type-label">Content format <select className="paper-inset rounded p-2" value={format} onChange={(event) => setFormat(event.target.value as "json" | "yaml")}><option value="json">JSON</option><option value="yaml">YAML</option></select></label>
            <label htmlFor={editorId} className="block type-label">Bulk records</label>
            <textarea id={editorId} className="paper-inset block w-full rounded p-3 font-mono type-body-sm" rows={14} spellCheck={false} value={draft} aria-invalid={Boolean(validation.error)} aria-describedby={`${editorId}-validation`} onChange={(event) => setDraft(event.target.value)} placeholder={format === "json" ? JSON.stringify([example], null, 2) : "# Paste a YAML list of records"} />
            <p id={`${editorId}-validation`} role="status" aria-live="polite" className={`type-body-sm ${validation.error ? "text-destructive" : "text-muted-foreground"}`}>
              {validation.error || (validation.records.length ? `${validation.records.length} records ready to review. Syntax and structure checks passed; server validation runs during installation.` : "Paste a list to check its syntax and accepted fields. Nothing is installed while typing.")}
            </p>
            <p className="type-body-sm text-muted-foreground">Accepted keys: {keys.join(", ")}. Use file upload for larger structures.</p>
            <Button disabled={!validation.records.length || Boolean(validation.error) || !contract.data} onClick={() => { setRecords(validation.records); setResults([]); setAttempted(false); setSource("paste"); setMode("preview") }}>Review records</Button>
          </div> : <>
            <p className="type-body">{records.length} records. Server validation runs when you select Install.</p>
            <pre className="paper-inset my-3 max-h-64 overflow-auto rounded p-3 type-body-sm">{JSON.stringify(records, null, 2)}</pre>
            <div aria-live="polite">{results.map((result) => <p className="type-body-sm" key={result.row}>{result.row}. {result.identity}: {result.status}</p>)}</div>
            {!!results.length && <Button variant="outline" onClick={() => downloadJson(`${kind}-bulk-results`, results)}>Download results</Button>}
            {source === "paste" && !attempted && <Button variant="outline" onClick={() => setMode("paste")}>Edit pasted records</Button>}
            <Button disabled={running || attempted || !records.length} onClick={() => void install()}>{running ? "Installing…" : "Install records"}</Button>
          </>}
          <div className="mt-4 flex justify-end"><Button variant="outline" disabled={running} onClick={() => setMode(null)}>Close</Button></div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  </div>
}
