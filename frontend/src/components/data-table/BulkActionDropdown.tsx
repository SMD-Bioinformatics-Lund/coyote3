import { useState } from "react"
import { Check } from "lucide-react"
import {
  FindingAction,
  FindingActionOption,
  findingBulkActionOptions,
} from "@/lib/finding-actions"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

const defaultActions = findingBulkActionOptions("small_variant")
export type BulkActionOptions = { includeAutomaticText?: boolean }

export function BulkActionDropdown({
  selectedCount,
  onAction,
  actions = defaultActions,
  isPending = false,
  automaticTextAvailable = false,
}: {
  selectedCount: number,
  onAction: (action: FindingAction, options?: BulkActionOptions) => void | Promise<unknown>
  actions?: FindingActionOption[]
  isPending?: boolean
  automaticTextAvailable?: boolean
}) {
  const [action, setAction] = useState<FindingAction | "">("")
  const [confirming, setConfirming] = useState(false)
  const [includeAutomaticText, setIncludeAutomaticText] = useState(false)

  if (selectedCount === 0) return null

  const handleApply = async () => {
    if (action) {
      await onAction(action, { includeAutomaticText })
      setAction("")
      setIncludeAutomaticText(false)
      setConfirming(false)
    }
  }

  const selectedAction = actions.find((item) => item.value === action)
  const canIncludeAutomaticText = automaticTextAvailable && action === "tier_3"

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
          if (nextAction !== "tier_3") setIncludeAutomaticText(false)
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
        {isPending ? <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <Check className="w-3.5 h-3.5" />}
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
                  onChange={(event) => setIncludeAutomaticText(event.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  <span className="block text-xs font-semibold text-foreground">Include automatic text</span>
                  <span className="block text-xs text-muted-foreground">Adds the established Tier III annotation generated from the finding context.</span>
                </span>
              </label>
            )}
          </>
        )}
        confirmLabel="Apply action"
        isPending={isPending}
        onConfirm={handleApply}
        onCancel={() => setConfirming(false)}
      />
    </div>
  )
}
