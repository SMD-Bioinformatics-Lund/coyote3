import { useId, useRef, useState, type RefObject } from "react"
import { icon as appIcon } from "@/lib/assets"
import { Button } from "@/components/ui/button"
import { MarkdownText } from "./MarkdownText"

export function MarkdownComposer({ id, value, onChange, maxLength = 5000, label,
  inputRef, invalid = false, compact = false, readOnly = false }: {
  id?: string; value: string; onChange: (value: string) => void; maxLength?: number | null
  label?: string; inputRef?: RefObject<HTMLTextAreaElement | null>; invalid?: boolean
  compact?: boolean; readOnly?: boolean
}) {
  const generatedId = useId()
  const internalInput = useRef<HTMLTextAreaElement>(null)
  const input = inputRef ?? internalInput
  const [preview, setPreview] = useState(false)
  const insert = (before: string, after = "", escape = false) => {
    const start = input.current?.selectionStart ?? value.length
    const end = input.current?.selectionEnd ?? start
    const selected = value.slice(start, end) || "text"
    const text = escape ? selected.replace(/([\\`*_{}[\]()#+\-.!>|~])/g, "\\$1") : before + selected + after
    const next = value.slice(0, start) + text + value.slice(end)
    if (maxLength != null && next.length > maxLength) return
    onChange(next)
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(start, start + text.length) })
  }
  return <div className="overflow-hidden rounded-lg border border-border bg-card">
    <div className="flex flex-wrap items-center gap-1 border-b border-border bg-muted p-1.5">
      {[
        { label: "Bold", icon: appIcon.bold, before: "**", after: "**" },
        { label: "Italic", icon: appIcon.italic, before: "*", after: "*" },
        { label: "Bulleted list", icon: appIcon.list, before: "\n- " },
        { label: "Quote", icon: appIcon.quote, before: "\n> " },
        { label: "Code", icon: appIcon.code, before: "`", after: "`" },
        { label: "Link", icon: appIcon.link, before: "[", after: "](https://)" },
        { label: "Escape Markdown", icon: appIcon.slash, before: "", escape: true },
      ].map(({ label, icon: Icon, before, after, escape }) => <Button key={label} type="button" size="icon-sm" variant="ghost" aria-label={label} title={label} disabled={preview || readOnly} onClick={() => insert(before, after, escape)}><Icon className="h-4 w-4" /></Button>)}
      <div className="ml-auto flex gap-1" role="group" aria-label="Message mode">
        <Button type="button" size="sm" disabled={readOnly} variant={!preview && !readOnly ? "secondary" : "ghost"} aria-pressed={!preview && !readOnly} onClick={() => setPreview(false)}>Write</Button>
        <Button type="button" size="sm" variant={preview || readOnly ? "secondary" : "ghost"} aria-pressed={preview || readOnly} onClick={() => setPreview(true)}>Preview</Button>
      </div>
    </div>
    {preview || readOnly ? <div aria-label={label ? `${label} preview` : undefined} className={`${compact ? "min-h-16" : "min-h-36"} overflow-auto p-3`}><MarkdownText text={value} className="break-words [overflow-wrap:anywhere]" /></div> : <textarea ref={input} id={id ?? generatedId} aria-label={label} aria-invalid={invalid} className={`${compact ? "min-h-16" : "min-h-36"} w-full resize-y bg-card p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring`} value={value} maxLength={maxLength ?? undefined} onChange={(event) => onChange(event.target.value)} />}
  </div>
}
