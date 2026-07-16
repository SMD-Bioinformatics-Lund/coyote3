import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"

export function JsonInspector({ value, maxHeight = "24rem" }: { value: unknown; maxHeight?: string }) {
  return (
    <pre
      className="overflow-auto rounded-lg border border-border bg-muted/30 p-3 text-xs leading-relaxed text-foreground"
      style={{ maxHeight }}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export function CollapsibleJson({
  title,
  value,
  defaultOpen = false,
}: {
  title: string
  value: unknown
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold hover:bg-muted/50"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {title}
      </button>
      {open && <div className="border-t border-border p-3"><JsonInspector value={value} /></div>}
    </div>
  )
}
