import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Ban, Bookmark, ShieldCheck, XCircle, XSquare } from "lucide-react"
import { api } from "@/lib/api"
import { FindingResourceType } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useSingleFindingFlag } from "@/hooks/useFindingActions"

export function VariantActionButtons({
  sampleId,
  resourceType = "small_variant",
  variant,
  onUpdate,
  compact = false,
}: {
  sampleId: string
  resourceType?: FindingResourceType
  variant: any
  onUpdate?: () => void
  compact?: boolean
}) {
  const [confirmBlacklist, setConfirmBlacklist] = useState(false)
  const flagMutation = useSingleFindingFlag(sampleId, resourceType)
  const queryClient = useQueryClient()
  const isFp = variant.fp
  const isIrrelevant = variant.irrelevant
  const isBlacklist = variant.blacklist && !variant.override_blacklist
  const isBlacklisted = Boolean(variant.blacklist || variant.blacklisted)
  const isInteresting = variant.interesting
  const isNoteworthy = variant.noteworthy
  const supportsIrrelevant = resourceType === "small_variant"
  const supportsBlacklist = resourceType === "small_variant"
  const supportsInteresting = resourceType === "small_variant" || resourceType === "cnv" || resourceType === "translocation"
  const supportsNoteworthy = resourceType === "cnv"
  const supportsBlacklistEntry = resourceType === "small_variant" && !isBlacklisted

  const blacklistMutation = useMutation({
    mutationFn: () => api.post(`/samples/${sampleId}/small-variants/${variant._id}/blacklist-entries`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["variant", sampleId, String(variant._id)] })
      queryClient.invalidateQueries({ queryKey: ["sample-variants", sampleId] })
      notifySuccess("Blacklist entry added", "The variant was added to the center blacklist.", "Variant actions")
      setConfirmBlacklist(false)
      onUpdate?.()
    },
    onError: (error) => notifyActionError("Unable to add blacklist entry", error, "Variant actions"),
  })

  const toggleStatus = async (
    flag: "false-positive" | "irrelevant" | "interesting" | "noteworthy" | "override-blacklist",
    apply: boolean,
  ) => {
    await flagMutation.mutateAsync({ resourceId: String(variant._id), flag, apply })
    if (onUpdate) onUpdate()
  }

  const buttonBase = compact
    ? "inline-flex h-7 w-7 items-center justify-center rounded-md border text-xs font-bold shadow-sm transition-colors duration-100 disabled:opacity-50"
    : "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-bold shadow-sm transition-colors duration-100 disabled:opacity-50"

  return (
    <div className={compact ? "flex items-center gap-1" : "flex flex-wrap items-center gap-1.5"}>
      <button 
        onClick={() => toggleStatus("false-positive", !isFp)}
        disabled={flagMutation.isPending}
        className={`${buttonBase} ${isFp ? 'border-fail/40 bg-fail/15 text-fail' : 'border-border bg-background hover:bg-fail/10 hover:text-fail'}`}
        title="Toggle False Positive"
      >
        <XCircle className="h-3.5 w-3.5" />
        {!compact && "FP"}
      </button>
      {supportsBlacklist && (
        <>
          {supportsBlacklistEntry && (
            <button
              onClick={() => setConfirmBlacklist(true)}
              disabled={blacklistMutation.isPending}
              className={`${buttonBase} border-border bg-background hover:bg-fail/10 hover:text-fail`}
              title="Add to blacklist"
            >
              <Ban className="h-3.5 w-3.5" />
              {!compact && "Add BL"}
            </button>
          )}
          {variant.blacklist && (
            <button
              onClick={() => toggleStatus("override-blacklist", isBlacklist)}
              disabled={flagMutation.isPending}
              className={`${buttonBase} ${isBlacklist ? 'border-validation/40 bg-validation/15 text-validation' : 'border-rna/35 bg-rna/10 text-rna hover:bg-rna/15'}`}
              title={isBlacklist ? "Override blacklist for this sample" : "Remove blacklist override"}
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              {!compact && (isBlacklist ? "Override BL" : "Clear BL Override")}
            </button>
          )}
        </>
      )}
      {supportsIrrelevant && (
        <button
          onClick={() => toggleStatus("irrelevant", !isIrrelevant)}
          disabled={flagMutation.isPending}
          className={`${buttonBase} ${isIrrelevant ? 'border-warn/40 bg-warn/15 text-warn' : 'border-border bg-background hover:bg-warn/10 hover:text-warn'}`}
        title="Toggle Irrelevant"
      >
          <XSquare className="h-3.5 w-3.5" />
          {!compact && "Ignore"}
        </button>
      )}
      {supportsInteresting && (
        <button
          onClick={() => toggleStatus("interesting", !isInteresting)}
          disabled={flagMutation.isPending}
          className={`${buttonBase} ${isInteresting ? 'border-pass/40 bg-pass/15 text-pass' : 'border-border bg-background hover:bg-pass/10 hover:text-pass'}`}
          title={resourceType === "small_variant" ? "Toggle interesting" : "Toggle report inclusion"}
      >
          <AlertCircle className="h-3.5 w-3.5" />
          {!compact && (resourceType === "small_variant" ? "Interesting" : isInteresting ? "Exclude" : "Report")}
        </button>
      )}
      {supportsNoteworthy && (
        <button
          onClick={() => toggleStatus("noteworthy", !isNoteworthy)}
          disabled={flagMutation.isPending}
          className={`${buttonBase} ${isNoteworthy ? 'border-tier2/40 bg-tier2/15 text-tier2' : 'border-border bg-background hover:bg-tier2/10 hover:text-tier2'}`}
          title="Toggle Noteworthy"
        >
          <Bookmark className="h-3.5 w-3.5" />
          {!compact && (isNoteworthy ? "Unnote" : "Note")}
        </button>
      )}
      {variant.override_blacklist && (
        <span className={compact ? "inline-flex h-7 w-7 items-center justify-center rounded-md border border-rna/30 bg-rna/10 text-xs font-bold text-rna" : "inline-flex items-center gap-1 rounded-lg border border-rna/30 bg-rna/10 px-2.5 py-1.5 text-xs font-bold text-rna"}>
          <ShieldCheck className="h-3.5 w-3.5" />
          {!compact && "Override"}
        </span>
      )}
      {confirmBlacklist && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-background/70 p-4">
          <div className="w-full max-w-sm rounded-xl border border-border bg-card p-4 shadow-lg">
            <h3 className="text-sm font-black text-foreground">Add variant to blacklist?</h3>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              This creates a center blacklist entry for this variant. Use override only when a blacklisted variant should remain visible for a specific sample.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmBlacklist(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-bold hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => blacklistMutation.mutate()}
                disabled={blacklistMutation.isPending}
                className="rounded-lg bg-fail px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
              >
                Add blacklist
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
