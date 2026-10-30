import { useState } from "react"
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
  selectedCount,
  onAction,
  actions = defaultActions,
  isPending = false,
  automaticTextAvailable = false,
  onPreviewAutomaticText,
}: {
  selectedCount: number,
  onAction: (action: FindingAction, options?: BulkActionOptions) => void | Promise<unknown>
  actions?: FindingActionOption[]
  isPending?: boolean
  automaticTextAvailable?: boolean
  onPreviewAutomaticText?: (action: FindingAction) => Promise<AnnotationPreviewRow[]>
}) {
  const [action, setAction] = useState<FindingAction | "">("")
  const [confirming, setConfirming] = useState(false)
  const [includeAutomaticText, setIncludeAutomaticText] = useState(false)
  const preview = useMutation({ mutationFn: async () => {
    if (!action || !onPreviewAutomaticText) throw new Error("Annotation preview is unavailable")
    return onPreviewAutomaticText(action)
  } })

  if (selectedCount === 0) return null

  const handleApply = async () => {
    if (action) {
      await onAction(action, { includeAutomaticText, ...(includeAutomaticText ? { annotationRuleHash: preview.data?.[0]?.content_hash } : {}) })
      setAction("")
      setIncludeAutomaticText(false)
      setConfirming(false)
    }
  }

  const selectedAction = actions.find((item) => item.value === action)
  const canIncludeAutomaticText = automaticTextAvailable && ["tier_1", "tier_2", "tier_3"].includes(action)

  return (
    <div className="relative flex items-center gap-2 bg-muted/30 px-3 py-1.5 rounded-lg border border-border animate-in fade-in zoom-in-95 duration-100">
      <span className="text-xs font-semibold text-muted-foreground mr-2">
        {selectedCount} selected
      </span>
      <select
        value={action}
        onChange={(e) => {
          const nextAction = e.target.value as FindingAction
          setAction(nextAction)
          setIncludeAutomaticText(false)
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
        disabled={!action || isPending}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-primary/10 text-primary hover:bg-primary hover:text-white transition-colors disabled:opacity-50 disabled:pointer-events-none"
      >
        {isPending ? <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <icon.check className="w-3.5 h-3.5" />}
        {isPending ? "Applying" : "Apply"}
      </button>
      <ConfirmationDialog
        open={confirming && Boolean(selectedAction)}
        title="Confirm bulk action"
        description={(
          <>
            Apply <strong className="text-foreground">{selectedAction?.label}</strong> to{" "}
            <strong className="text-foreground">{selectedCount}</strong> selected finding(s)?
            This changes persisted clinical review state.
            {canIncludeAutomaticText && (
              <label className="mt-4 flex cursor-pointer items-start gap-2 rounded-md border border-border bg-background p-2.5 text-left">
                <input
                  type="checkbox"
                  aria-label="Include automatic text"
                  checked={includeAutomaticText}
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
              <Button type="button" size="sm" variant="outline" disabled={preview.isPending} onClick={() => preview.mutate()}>Preview annotation text</Button>
              {preview.isPending && <p role="status" className="type-meta">Generating annotation preview…</p>}
              {preview.error && <p role="alert" className="type-body-sm text-destructive">{preview.error instanceof Error ? preview.error.message : "Preview failed"}</p>}
              {preview.data && <><p className="type-meta">{preview.data.filter(item => item.text).length} with annotation text; {preview.data.filter(item => !item.text).length} without a matching template. All selected findings receive the chosen tier.</p><div className="max-h-64 space-y-2 overflow-y-auto">{preview.data.map(item => <div key={item.resource_id} className="paper-inset rounded-lg p-2"><p className="type-label">{item.gene || "Finding"} · {item.rule_id || "No matching template"}</p>{item.text && <MarkdownText text={item.text} />}</div>)}</div></>}
            </div>}
          </>
        )}
        confirmLabel="Apply action"
        isPending={isPending}
        confirmDisabled={includeAutomaticText && (!preview.data || preview.isPending || preview.data.length !== selectedCount)}
        onConfirm={handleApply}
        onCancel={() => { setConfirming(false); preview.reset() }}
      />
    </div>
  )
}
