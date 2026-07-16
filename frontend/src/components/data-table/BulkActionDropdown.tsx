import { useState } from "react"
import { Check, X } from "lucide-react"
import { FindingAction } from "@/lib/finding-actions"

export type BulkActionOption = {
  value: FindingAction
  label: string
}

const defaultActions: BulkActionOption[] = [
  { value: "tier_1", label: "Classify as Tier 1" },
  { value: "tier_2", label: "Classify as Tier 2" },
  { value: "tier_3", label: "Classify as Tier 3" },
  { value: "tier_4", label: "Classify as Tier 4" },
  { value: "fp", label: "Mark False Positive" },
  { value: "unfp", label: "Unmark False Positive" },
  { value: "irrelevant", label: "Mark Irrelevant" },
  { value: "relevant", label: "Unmark Irrelevant" },
  { value: "interesting", label: "Mark Interesting" },
  { value: "uninteresting", label: "Unmark Interesting" },
]

export function BulkActionDropdown({ 
  selectedCount, 
  onAction,
  actions = defaultActions,
  isPending = false,
}: { 
  selectedCount: number, 
  onAction: (action: FindingAction) => void | Promise<unknown>
  actions?: BulkActionOption[]
  isPending?: boolean
}) {
  const [action, setAction] = useState<FindingAction | "">("")
  const [confirming, setConfirming] = useState(false)

  if (selectedCount === 0) return null

  const handleApply = async () => {
    if (action) {
      await onAction(action)
      setAction("")
      setConfirming(false)
    }
  }

  const selectedAction = actions.find((item) => item.value === action)

  return (
    <div className="relative flex items-center gap-2 bg-muted/30 px-3 py-1.5 rounded-lg border border-border animate-in fade-in zoom-in-95 duration-100">
      <span className="text-xs font-semibold text-muted-foreground mr-2">
        {selectedCount} selected
      </span>
      <select 
        value={action} 
        onChange={(e) => setAction(e.target.value as FindingAction)}
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
      {confirming && selectedAction && (
        <div className="absolute z-50 mt-24 w-[min(28rem,calc(100vw-2rem))] rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-lg">
          <div className="mb-2 text-sm font-black">Confirm bulk action</div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Apply <span className="font-bold text-foreground">{selectedAction.label}</span> to{" "}
            <span className="font-bold text-foreground">{selectedCount}</span> selected finding(s)?
          </p>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-bold hover:bg-muted"
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={isPending}
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" />
              Confirm
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
