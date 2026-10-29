import { useId, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { icon } from "@/lib/assets"
import { downloadJson } from "@/lib/json-download"

type Document = Record<string, unknown>

/** Transfer editable configuration; importing stages a document for normal validation. */
export function ConfigurationTransfer({ label, filename, document, onImport, fields,
  required = [], disabled = false, importLabel = "Import JSON" }: {
  label: string
  filename: string
  document?: unknown
  onImport?: (document: Document) => void | Promise<void>
  fields?: readonly string[]
  required?: readonly string[]
  disabled?: boolean
  importLabel?: string
}) {
  const input = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const [error, setError] = useState("")
  const [reading, setReading] = useState(false)
  return <div className="flex flex-wrap items-center gap-2">
    {onImport && <>
      <input ref={input} type="file" accept="application/json,.json" className="sr-only"
        aria-label={`Import ${label} JSON`} aria-describedby={error ? errorId : undefined}
        disabled={disabled || reading} onChange={async event => {
          const file = event.target.files?.[0]
          event.target.value = ""
          if (!file) return
          setError(""); setReading(true)
          try {
            if (file.size > 1024 * 1024) throw new Error("File must be no larger than 1 MiB")
            const value: unknown = JSON.parse(await file.text())
            if (!value || typeof value !== "object" || Array.isArray(value)) {
              throw new Error("Choose a JSON object exported for this resource")
            }
            const record = value as Document
            const unknown = fields && Object.keys(record).filter(key => !fields.includes(key))
            if (unknown?.length) throw new Error(`Unsupported fields: ${unknown.join(", ")}`)
            const missing = required.filter(key => record[key] == null)
            if (missing.length) throw new Error(`Missing fields: ${missing.join(", ")}`)
            await onImport(record)
          } catch (failure) {
            setError(failure instanceof SyntaxError ? "The selected file is not valid JSON."
              : failure instanceof Error ? failure.message : "Unable to import configuration")
          } finally { setReading(false) }
        }} />
      <Button type="button" variant="outline" disabled={disabled || reading}
        onClick={() => input.current?.click()}><icon.upload aria-hidden="true" />{importLabel}</Button>
    </>}
    {document !== undefined && <Button type="button" variant="outline" disabled={disabled || reading}
      onClick={() => downloadJson(filename, document)}><icon.download aria-hidden="true" />Export JSON</Button>}
    {error && <p id={errorId} role="alert" className="w-full type-body-sm text-destructive">{error}</p>}
  </div>
}
