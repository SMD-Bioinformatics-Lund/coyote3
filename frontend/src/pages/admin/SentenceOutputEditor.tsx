import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useEffect, useRef, useState } from "react"
import type { FactDefinition, OutputNode } from "./clinical-rules-types"
import { parseSentence, sentenceTemplate } from "./rule-sentence"

export function SentenceOutputEditor({ nodes, facts, onChange, onErrorChange }: {
  nodes: OutputNode[]; facts: FactDefinition[]; onChange: (nodes: OutputNode[]) => void
  onErrorChange?: (error: string) => void
}) {
  const [template, setTemplate] = useState(() => sentenceTemplate(nodes))
  const [error, setError] = useState("")
  const [search, setSearch] = useState("")
  const textarea = useRef<HTMLTextAreaElement>(null)
  const emitted = useRef(JSON.stringify(nodes))
  useEffect(() => {
    const incoming = JSON.stringify(nodes)
    if (incoming !== emitted.current) {
      emitted.current = incoming
      setTemplate(sentenceTemplate(nodes))
      setError("")
      onErrorChange?.("")
    }
  }, [nodes, onErrorChange])
  const update = (text: string) => {
    setTemplate(current => ({ ...current, text }))
    try {
      const output = parseSentence(text, template.tokens, facts)
      setError("")
      onErrorChange?.("")
      emitted.current = JSON.stringify(output)
      onChange(output)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Check the inline placeholders."
      setError(message)
      onErrorChange?.(message)
    }
  }
  const insert = (path: string) => {
    const start = textarea.current?.selectionStart ?? template.text.length
    const end = textarea.current?.selectionEnd ?? start
    const token = `{{${path}}}`
    update(template.text.slice(0, start) + token + template.text.slice(end))
    requestAnimationFrame(() => {
      textarea.current?.focus()
      textarea.current?.setSelectionRange(start + token.length, start + token.length)
    })
  }
  return <div className="space-y-2">
    <p className="type-body-sm text-muted-foreground">Write the complete sentence here. Insert values at the cursor, for example {"{{asp.display_name}}"}. Conditions above control when this sentence appears.</p>
    <textarea ref={textarea} aria-label="Report sentence" aria-invalid={!!error} className="paper-inset min-h-36 w-full resize-y rounded-lg p-3 type-body" value={template.text} onChange={event => update(event.target.value)} />
    {error && <p role="alert" className="type-body-sm text-destructive">{error} This edit is not saved until corrected.</p>}
    <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer type-body font-medium">Insert value at cursor</summary>
      <Input aria-label="Find inline value" className="mt-2" value={search} onChange={event => setSearch(event.target.value)} placeholder="Find assay name, gene count, VAF…" />
      <div className="mt-2 flex max-h-48 flex-wrap gap-1 overflow-auto">{facts.filter(fact => fact.kind !== "object_list" && `${fact.path} ${fact.label}`.toLowerCase().includes(search.toLowerCase())).map(fact => <Button key={fact.path} type="button" variant="outline" size="sm" title={fact.path} onMouseDown={event => event.preventDefault()} onClick={() => insert(fact.path)}>{fact.label}</Button>)}</div>
    </details>
  </div>
}
