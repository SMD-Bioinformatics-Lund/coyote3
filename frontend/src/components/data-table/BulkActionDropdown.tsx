import { useEffect, useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { Button } from "@/components/ui/button"
import { icon } from "@/lib/assets"
import {
  FindingAction,
  FindingActionOption,
  findingBulkActionOptions,
  type AnnotationPreviewRow,
} from "@/lib/finding-actions"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

const defaultActions = findingBulkActionOptions("small_variant")
export type BulkActionOptions = { includeAutomaticText?: boolean; annotationRuleHash?: string }

export function BulkActionDropdown({
  selectedIds,
  onAction,
  actions = defaultActions,
  isPending = false,
  automaticTextAvailable = false,
  onPreviewAutomaticText,
}: {
  selectedIds: string[],
  onAction: (action: FindingAction, options?: BulkActionOptions) => void | Promise<unknown>
  actions?: FindingActionOption[]
  isPending?: boolean
  automaticTextAvailable?: boolean
  onPreviewAutomaticText?: (action: FindingAction) => Promise<AnnotationPreviewRow[]>
}) {
  const [action, setAction] = useState<FindingAction | "">("")
  const [confirming, setConfirming] = useState(false)
  const [includeAutomaticText, setIncludeAutomaticText] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyError, setApplyError] = useState("")
  const applyLock = useRef(false)
  const busy = isPending || applying
  const selectedCount = selectedIds.length
  const selectionKey = JSON.stringify([...selectedIds].sort())
  const preview = useMutation({ mutationFn: async ({ requestedAction }: { requestedAction: FindingAction | ""; selectionKey: string }) => {
    if (!requestedAction || !onPreviewAutomaticText) throw new Error("Annotation preview is unavailable")
    return onPreviewAutomaticText(requestedAction)
  } })
  const resetPreview = preview.reset
  useEffect(() => {
    setConfirming(false)
    setIncludeAutomaticText(false)
    setApplyError("")
    resetPreview()
  }, [selectionKey, resetPreview])
  const selectedAction = actions.find((item) => item.value === action)
  const canIncludeAutomaticText = automaticTextAvailable && ["tier_1", "tier_2", "tier_3"].includes(action)
  const validPreview = Boolean(preview.data && !preview.isPending && !preview.isError
    && preview.variables?.selectionKey === selectionKey && preview.variables.requestedAction === action
    && JSON.stringify(preview.data.map(row => row.resource_id).sort()) === selectionKey
    && preview.data[0]?.content_hash && preview.data.every(row => row.content_hash === preview.data?.[0]?.content_hash))
  const confirmDisabled = !selectedAction || busy || (includeAutomaticText && (!canIncludeAutomaticText || !validPreview))

  if (selectedCount === 0) return null

  const handleApply = async () => {
    if (action && !confirmDisabled && !applyLock.current) {
      applyLock.current = true
      setApplying(true)
      setApplyError("")
      try {
        await onAction(action, { includeAutomaticText, ...(includeAutomaticText ? { annotationRuleHash: preview.data?.[0]?.content_hash } : {}) })
        setAction("")
        setIncludeAutomaticText(false)
        setConfirming(false)
      } catch (error) {
        setApplyError(error instanceof Error ? error.message : "The bulk action could not be completed.")
        // A failed write may reflect a newer publication; require a fresh preview.
        preview.reset()
      } finally {
        applyLock.current = false
        setApplying(false)
      }
    }
  }

  return (
    <div className="relative flex items-center gap-2 bg-muted/30 px-3 py-1.5 rounded-lg border border-border animate-in fade-in zoom-in-95 duration-100">
      <span className="text-xs font-semibold text-muted-foreground mr-2">
        {selectedCount} selected
      </span>
      <select
        disabled={busy}
        value={action}
        onChange={(e) => {
          const nextAction = e.target.value as FindingAction
          setAction(nextAction)
          setIncludeAutomaticText(false)
          setApplyError("")
          preview.reset()
        }}
        className="text-sm p-1.5 rounded-md border border-input bg-background w-40 focus:outline-none focus:ring-1 focus:ring-primary/50"
      >
        <option value="" disabled>Select Action...</option>
        {actions.map((item) => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>
      <button
        onClick={() => setConfirming(true)}
        disabled={!selectedAction || busy}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-primary/10 text-primary hover:bg-primary hover:text-white transition-colors disabled:opacity-50 disabled:pointer-events-none"
      >
        {busy ? <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <icon.check className="w-3.5 h-3.5" />}
        {busy ? "Applying" : "Apply"}
      </button>
      <ConfirmationDialog
        open={confirming && Boolean(selectedAction)}
        title="Confirm bulk action"
        description={(
          <>
            Apply <strong className="text-foreground">{selectedAction?.label}</strong> to{" "}
            <strong className="text-foreground">{selectedCount}</strong> selected finding(s)?
            This changes persisted clinical review state.
            {applyError && <p role="alert" className="mt-3 type-body-sm text-destructive">{applyError}</p>}
            {canIncludeAutomaticText && (
              <label className="mt-4 flex cursor-pointer items-start gap-2 rounded-md border border-border bg-background p-2.5 text-left">
                <input
                  type="checkbox"
                  aria-label="Include automatic text"
                  checked={includeAutomaticText}
                  disabled={busy}
                  onChange={(event) => { setIncludeAutomaticText(event.target.checked); preview.reset() }}
                  className="mt-0.5"
                />
                <span>
                  <span className="block text-xs font-semibold text-foreground">Include automatic text</span>
                  <span className="block text-xs text-muted-foreground">Uses the first matching published annotation template for each finding and the selected tier.</span>
                </span>
              </label>
            )}
            {canIncludeAutomaticText && includeAutomaticText && <div className="mt-3 space-y-2">
              <Button type="button" size="sm" variant="outline" disabled={busy || preview.isPending} onClick={() => preview.mutate({ requestedAction: action, selectionKey })}>Preview annotation text</Button>
              {preview.isPending && <p role="status" className="type-meta">Generating annotation preview…</p>}
              {preview.error && <p role="alert" className="type-body-sm text-destructive">{preview.error instanceof Error ? preview.error.message : "Preview failed"}</p>}
              {preview.data && !preview.isPending && !validPreview && <p role="alert" className="type-body-sm text-destructive">The preview does not match the selected findings and one rule version. Preview again before applying.</p>}
            {preview.data && validPreview && <><p className="type-meta">{preview.data.filter(item => item.text).length} with annotation text; {preview.data.filter(item => !item.text).length} without a matching template. All selected findings receive the chosen tier.</p><div className="max-h-64 space-y-2 overflow-y-auto">{preview.data.map(item => <div key={item.resource_id} className="paper-inset rounded-lg p-2"><p className="type-label">{item.gene || "Finding"} · {item.rule_id || "No matching template"}</p>{item.text && <MarkdownText text={item.text} />}</div>)}</div></>}
            </div>}
          </>
        )}
        confirmLabel="Apply action"
        isPending={busy}
        confirmDisabled={confirmDisabled}
        onConfirm={handleApply}
        onCancel={() => { setConfirming(false); preview.reset() }}
      />
    </div>
  )
}
