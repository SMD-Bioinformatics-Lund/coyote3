import {
  parseCellValue
} from "@/pages/admin/resource-list"
import { X } from "lucide-react"


export function ObjectFieldEditor({
  value,
  onChange,
  disabled,
}: {
  value: any
  onChange: (next: Record<string, any>) => void
  disabled?: boolean
}) {
  const objectValue = value && typeof value === "object" && !Array.isArray(value) ? value : {}
  const rows = Object.entries(objectValue)

  const updateKey = (oldKey: string, newKey: string) => {
    const next: Record<string, any> = {}
    rows.forEach(([key, rowValue]) => {
      next[key === oldKey ? newKey : key] = rowValue
    })
    onChange(next)
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-background/60 p-2">
      {rows.length === 0 && <p className="text-xs text-muted-foreground">No entries configured.</p>}
      {rows.map(([key, rowValue]) => (
        <div key={key} className="grid gap-2 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)_auto]">
          <input
            value={key}
            disabled={disabled}
            onChange={(event) => updateKey(key, event.target.value)}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="Key"
          />
          <input
            value={typeof rowValue === "object" ? JSON.stringify(rowValue) : String(rowValue ?? "")}
            disabled={disabled}
            onChange={(event) => onChange({ ...objectValue, [key]: parseCellValue(event.target.value) })}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="Value"
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              const next = { ...objectValue }
              delete next[key]
              onChange(next)
            }}
            className="rounded-md border border-border p-1.5 text-destructive hover:bg-destructive/10 disabled:opacity-50"
            title="Remove entry"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange({ ...objectValue, [`key_${rows.length + 1}`]: "" })}
        className="rounded-md border border-border px-2 py-1 text-xs font-semibold hover:bg-muted disabled:opacity-50"
      >
        Add entry
      </button>
    </div>
  )
}
