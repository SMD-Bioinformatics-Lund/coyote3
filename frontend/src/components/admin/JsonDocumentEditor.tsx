import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type UIEvent } from "react"
import { AlertCircle, Braces, CheckCircle2, RotateCcw, Save, WandSparkles } from "lucide-react"

import { validateJsonDocument } from "./json-document-validation"
import { Button } from "@/components/ui/button"

interface JsonDocumentEditorProps {
  document: Record<string, unknown>
  readOnly?: boolean
  isSaving?: boolean
  serverError?: string
  onCancel: () => void
  onSave: (document: Record<string, unknown>) => void
}

export function JsonDocumentEditor({
  document,
  readOnly = false,
  isSaving = false,
  serverError = "",
  onCancel,
  onSave,
}: JsonDocumentEditorProps) {
  const initialSource = useMemo(() => JSON.stringify(document, null, 2), [document])
  const [source, setSource] = useState(initialSource)
  const lineNumbersRef = useRef<HTMLPreElement>(null)
  const diagnosticsRef = useRef<HTMLDivElement>(null)

  useEffect(() => setSource(initialSource), [initialSource])

  const validation = useMemo(() => validateJsonDocument(source), [source])
  const isDirty = source !== initialSource
  const lineCount = source ? source.split("\n").length : 1
  const lineNumbers = useMemo(
    () => Array.from({ length: lineCount }, (_, index) => index + 1).join("\n"),
    [lineCount],
  )
  const diagnosticLines = useMemo(
    () =>
      Array.from({ length: lineCount }, (_, index) => {
        const line = index + 1
        const diagnostics = validation.valid
          ? []
          : validation.diagnostics.filter((diagnostic) => diagnostic.line === line)
        if (!diagnostics.length) {
          return <div key={line} className="h-6" aria-hidden="true" />
        }
        const message = diagnostics.map((diagnostic) => diagnostic.message).join(" ")
        const columns = diagnostics.map((diagnostic) => diagnostic.column).join(", ")
        return (
          <div
            key={line}
            className="flex h-6 min-w-0 items-center gap-1.5 px-2 text-xs font-medium text-destructive"
            title={message}
            role="alert"
          >
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span className="shrink-0">Line {line}:{columns}</span>
            <span className="truncate">{message}</span>
          </div>
        )
      }),
    [lineCount, validation],
  )

  const handleEditorKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (readOnly || event.key !== "Tab") return
    event.preventDefault()
    const editor = event.currentTarget
    const nextSource = `${source.slice(0, editor.selectionStart)}  ${source.slice(editor.selectionEnd)}`
    const nextCursor = editor.selectionStart + 2
    setSource(nextSource)
    requestAnimationFrame(() => editor.setSelectionRange(nextCursor, nextCursor))
  }

  const formatDocument = () => {
    if (!validation.valid) return
    setSource(JSON.stringify(validation.document, null, 2))
  }

  const syncLineNumberScroll = (event: UIEvent<HTMLTextAreaElement>) => {
    if (lineNumbersRef.current) lineNumbersRef.current.scrollTop = event.currentTarget.scrollTop
    if (diagnosticsRef.current) diagnosticsRef.current.scrollTop = event.currentTarget.scrollTop
  }

  return (
    <section className="surface-panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="rounded-lg bg-primary/10 p-2 text-primary">
            <Braces className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-base font-semibold">Sample JSON document</h2>
            <p className="text-xs text-muted-foreground">
              JSON syntax is checked locally. The complete sample contract is checked by the API when saved.
            </p>
          </div>
        </div>
        {!readOnly && (
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={formatDocument} disabled={!validation.valid || isSaving}>
              <WandSparkles className="h-4 w-4" />
              Format JSON
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => setSource(initialSource)} disabled={!isDirty || isSaving}>
              <RotateCcw className="h-4 w-4" />
              Reset
            </Button>
          </div>
        )}
      </div>

      <div className="p-4">
        <div className="flex min-h-[60vh] overflow-hidden rounded-lg border border-input bg-background focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
          <pre
            ref={lineNumbersRef}
            aria-hidden="true"
            className="w-14 shrink-0 overflow-hidden border-r border-border bg-muted/45 px-3 py-4 text-right font-[ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace] type-body-sm leading-6 text-muted-foreground"
          >
            {lineNumbers}
          </pre>
          <textarea
            aria-label="Sample JSON"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            onKeyDown={handleEditorKeyDown}
            onScroll={syncLineNumberScroll}
            readOnly={readOnly}
            spellCheck={false}
            className="min-h-[60vh] min-w-0 flex-1 resize-y border-0 bg-transparent p-4 font-[ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace] type-body-sm leading-6 text-foreground outline-none read-only:cursor-default read-only:bg-muted/20"
          />
          {!validation.valid && (
            <div
              ref={diagnosticsRef}
              aria-label="JSON diagnostics"
              className="w-[min(34vw,26rem)] shrink-0 overflow-hidden border-l border-destructive/25 bg-destructive/5 py-4"
            >
              {diagnosticLines}
            </div>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0" aria-live="polite">
            {validation.valid ? (
              <p className="flex items-center gap-2 text-xs font-semibold text-success">
                <CheckCircle2 className="h-4 w-4" />
                Valid JSON object
              </p>
            ) : (
              <p className="text-xs font-medium text-destructive">
                Correct the highlighted JSON line before saving.
              </p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">{lineCount} lines · {source.length.toLocaleString()} characters</p>
          </div>

          {!readOnly && (
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSaving}>Cancel</Button>
              <Button
                type="button"
                onClick={() => validation.valid && onSave(validation.document)}
                disabled={!validation.valid || !isDirty || isSaving}
              >
                <Save className="h-4 w-4" />
                {isSaving ? "Saving" : "Save sample"}
              </Button>
            </div>
          )}
        </div>

        {serverError && (
          <div className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" role="alert">
            {serverError}
          </div>
        )}
      </div>
    </section>
  )
}
