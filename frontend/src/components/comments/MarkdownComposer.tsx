import { useRef, useState } from "react"
import { Bold, Italic, List, Link, Code, Quote, Slash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { MarkdownText } from "./MarkdownText"

export function MarkdownComposer({ id, value, onChange, maxLength = 5000 }: {
  id: string; value: string; onChange: (value: string) => void; maxLength?: number
}) {
  const input = useRef<HTMLTextAreaElement>(null)
  const [preview, setPreview] = useState(false)
  const insert = (before: string, after = "", escape = false) => {
    const start = input.current?.selectionStart ?? value.length
    const end = input.current?.selectionEnd ?? start
    const selected = value.slice(start, end) || "text"
    const text = escape ? selected.replace(/([\\`*_{}[\]()#+\-.!>|~])/g, "\\$1") : before + selected + after
    const next = value.slice(0, start) + text + value.slice(end)
    if (next.length > maxLength) return
    onChange(next)
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(start, start + text.length) })
  }
  return <div className="overflow-hidden rounded-lg border border-border bg-card">
    <div className="flex flex-wrap items-center gap-1 border-b border-border bg-muted p-1.5">
      {[
        { label: "Bold", icon: Bold, before: "**", after: "**" },
        { label: "Italic", icon: Italic, before: "*", after: "*" },
        { label: "Bulleted list", icon: List, before: "\n- " },
        { label: "Quote", icon: Quote, before: "\n> " },
        { label: "Code", icon: Code, before: "`", after: "`" },
        { label: "Link", icon: Link, before: "[", after: "](https://)" },
        { label: "Escape Markdown", icon: Slash, before: "", escape: true },
      ].map(({ label, icon: Icon, before, after, escape }) => <Button key={label} type="button" size="icon-sm" variant="ghost" aria-label={label} title={label} disabled={preview} onClick={() => insert(before, after, escape)}><Icon className="h-4 w-4" /></Button>)}
      <div className="ml-auto flex gap-1" role="group" aria-label="Message mode">
        <Button type="button" size="sm" variant={!preview ? "secondary" : "ghost"} aria-pressed={!preview} onClick={() => setPreview(false)}>Write</Button>
        <Button type="button" size="sm" variant={preview ? "secondary" : "ghost"} aria-pressed={preview} onClick={() => setPreview(true)}>Preview</Button>
      </div>
    </div>
    {preview ? <div className="min-h-36 overflow-auto p-3"><MarkdownText text={value} className="break-words [overflow-wrap:anywhere]" /></div> : <textarea ref={input} id={id} className="min-h-36 w-full resize-y bg-card p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" value={value} maxLength={maxLength} onChange={(event) => onChange(event.target.value)} />}
  </div>
}
