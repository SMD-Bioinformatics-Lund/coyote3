import { useEffect, useId, useRef, useState } from "react"
import { Bold, Italic, Underline, List, ListOrdered, Link, Unlink, RemoveFormatting } from "lucide-react"
import { sanitizeRichText } from "@/lib/safe-html"
import { Button } from "./button"
import { Input } from "./input"

/** Edit sanitized HTML with formatting controls and an explicit safe-link form. */
export function RichTextEditor({ label, value, onChange }: {
  label: string; value: string; onChange: (value: string) => void
}) {
  const id = useId()
  const editor = useRef<HTMLDivElement>(null)
  const selection = useRef<Range | null>(null)
  const [linkOpen, setLinkOpen] = useState(false)
  const [url, setUrl] = useState("")
  const [error, setError] = useState("")
  useEffect(() => {
    const node = editor.current
    const clean = sanitizeRichText(value)
    if (node && node.innerHTML !== clean) node.innerHTML = clean
  }, [value])
  const remember = () => {
    const selected = window.getSelection()
    if (selected?.rangeCount && editor.current?.contains(selected.anchorNode)) {
      selection.current = selected.getRangeAt(0).cloneRange()
    }
  }
  const emit = () => onChange(sanitizeRichText(editor.current?.innerHTML || ""))
  const apply = (command: string, argument?: string) => {
    if (editor.current?.closest("fieldset[disabled]")) return
    editor.current?.focus()
    if (selection.current && editor.current?.contains(selection.current.commonAncestorContainer)) {
      const selected = window.getSelection()
      selected?.removeAllRanges()
      selected?.addRange(selection.current)
    }
    document.execCommand(command, false, argument)
    remember()
    emit()
  }
  const addLink = () => {
    const target = url.trim()
    try {
      const parsed = new URL(target)
      if (!["https:", "http:", "mailto:"].includes(parsed.protocol)) throw new Error("protocol")
    } catch {
      setError("Enter an https://, http:// or mailto: link.")
      return
    }
    if (!selection.current || selection.current.collapsed) {
      setError("Select the text to link in the editor first.")
      return
    }
    apply("createLink", target)
    setLinkOpen(false)
    setUrl("")
    setError("")
  }
  return <div className="space-y-1">
    <p id={id} className="type-label">{label}</p>
    <div className="overflow-hidden rounded-lg border border-input bg-background">
      <div role="group" aria-label={`${label} formatting`} className="flex flex-wrap gap-1 border-b border-border bg-muted/30 p-1">
        {([
          ["bold", "Bold", Bold], ["italic", "Italic", Italic], ["underline", "Underline", Underline],
          ["insertUnorderedList", "Bullet list", List], ["insertOrderedList", "Numbered list", ListOrdered],
          ["unlink", "Remove link", Unlink], ["removeFormat", "Clear formatting", RemoveFormatting],
        ] as const).map(([command, title, Icon]) => <Button key={command} type="button" size="icon-sm" variant="ghost"
          aria-label={title} title={title} onMouseDown={(event) => event.preventDefault()} onClick={() => apply(command)}><Icon /></Button>)}
        <Button type="button" size="icon-sm" variant="ghost" aria-label="Insert link" title="Insert link"
          onMouseDown={(event) => event.preventDefault()} onClick={() => { remember(); setLinkOpen(true); setError("") }}><Link /></Button>
      </div>
      {linkOpen && <div className="space-y-2 border-b border-border p-2">
        <div className="flex flex-wrap gap-2"><Input aria-label={`${label} link URL`} placeholder="https://example.org" value={url} onChange={(event) => setUrl(event.target.value)} />
          <Button type="button" size="sm" onClick={addLink}>Apply link</Button>
          <Button type="button" size="sm" variant="outline" onClick={() => setLinkOpen(false)}>Cancel</Button></div>
        {error && <p role="alert" className="type-body-sm text-destructive">{error}</p>}
      </div>}
      <div ref={editor} role="textbox" aria-labelledby={id} aria-multiline="true" contentEditable suppressContentEditableWarning
        className="min-h-28 p-3 type-body focus-visible:outline-2 focus-visible:outline-ring [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6"
        onInput={emit} onKeyUp={remember} onMouseUp={remember}
        onBeforeInput={(event) => { if (editor.current?.closest("fieldset[disabled]")) event.preventDefault() }}
        onPaste={(event) => { event.preventDefault(); remember(); apply("insertText", event.clipboardData.getData("text/plain")) }}
        onDrop={(event) => event.preventDefault()} />
    </div>
  </div>
}
