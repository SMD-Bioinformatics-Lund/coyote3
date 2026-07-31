import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Ban, Bookmark, FileCheck2, ShieldCheck, XCircle, XSquare } from "lucide-react"
import { api } from "@/lib/api"
import { FindingResourceType } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useSingleFindingFlag } from "@/hooks/useFindingActions"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

type FindingFlag = "false-positive" | "irrelevant" | "interesting" | "noteworthy" | "override-blacklist"

type PendingFlagAction = {
  title: string
  description: string
  confirmLabel: string
  flag: FindingFlag
  apply: boolean
}

export function VariantActionButtons({
  sampleId,
  resourceType = "small_variant",
  variant,
  onUpdate,
  compact = false,
  showReportLabel = false,
}: {
  sampleId: string
  resourceType?: FindingResourceType
  variant: any
  onUpdate?: () => void
  compact?: boolean
  showReportLabel?: boolean
}) {
  const [confirmBlacklist, setConfirmBlacklist] = useState(false)
  const [pendingFlagAction, setPendingFlagAction] = useState<PendingFlagAction | null>(null)
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
      queryClient.invalidateQueries({ queryKey: ["sample-comment-suggestion", sampleId] })
      notifySuccess("Blacklist entry added", "The variant was added to the center blacklist.", "Variant actions")
      setConfirmBlacklist(false)
      onUpdate?.()
    },
    onError: (error) => notifyActionError("Unable to add blacklist entry", error, "Variant actions"),
  })

  const toggleStatus = async (
    flag: FindingFlag,
    apply: boolean,
  ) => {
    await flagMutation.mutateAsync({ resourceId: String(variant._id), flag, apply })
    if (onUpdate) onUpdate()
  }

  const confirmFlagAction = async () => {
    if (!pendingFlagAction) return
    try {
      await toggleStatus(pendingFlagAction.flag, pendingFlagAction.apply)
      setPendingFlagAction(null)
    } catch {
      // The mutation hook emits the user-facing error notification.
    }
  }

  const buttonBase = compact
    ? "paper-raised-control inline-flex h-7 w-7 items-center justify-center rounded-lg border text-xs font-bold transition-[transform,box-shadow,background-color,border-color,color] duration-100 disabled:opacity-50"
    : "paper-raised-control inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-bold transition-[transform,box-shadow,background-color,border-color,color] duration-100 disabled:opacity-50"
  const labeledCompactReport = compact && showReportLabel && resourceType !== "small_variant"
  const reportButtonBase = labeledCompactReport
    ? "paper-raised-control inline-flex h-7 items-center justify-center gap-1 rounded-lg border px-2 text-xs font-bold transition-[transform,box-shadow,background-color,border-color,color] duration-100 disabled:opacity-50"
    : buttonBase

  return (
    <div className={compact ? "flex items-center gap-1" : "flex flex-wrap items-center gap-1.5"}>
      <button
        onClick={() => setPendingFlagAction({
          title: isFp ? "Remove false-positive flag?" : "Mark finding as false positive?",
          description: isFp
            ? "The finding will return to the active review set."
            : "The finding will be de-emphasized and excluded where false-positive findings are filtered.",
          confirmLabel: isFp ? "Remove FP flag" : "Mark false positive",
          flag: "false-positive",
          apply: !isFp,
        })}
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
              onClick={() => setPendingFlagAction({
                title: isBlacklist ? "Override blacklist match?" : "Remove blacklist override?",
                description: isBlacklist
                  ? "This finding will remain available for review in this sample despite the center blacklist match."
                  : "The center blacklist match will apply to this finding again.",
                confirmLabel: isBlacklist ? "Override blacklist" : "Remove override",
                flag: "override-blacklist",
                apply: isBlacklist,
              })}
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
          onClick={() => setPendingFlagAction({
            title: isIrrelevant ? "Restore finding to review?" : "Mark finding as irrelevant?",
            description: isIrrelevant
              ? "The finding will return to the active review set."
              : "The finding will be de-emphasized as irrelevant for the current review.",
            confirmLabel: isIrrelevant ? "Restore finding" : "Mark irrelevant",
            flag: "irrelevant",
            apply: !isIrrelevant,
          })}
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
          onClick={() => setPendingFlagAction({
            title: resourceType === "small_variant"
              ? (isInteresting ? "Remove interesting flag?" : "Mark finding as interesting?")
              : (isInteresting ? "Exclude finding from report?" : "Include finding in report?"),
            description: resourceType === "small_variant"
              ? "This changes the finding's clinical review state."
              : `This will ${isInteresting ? "remove the finding from" : "add the finding to"} the reportable set.`,
            confirmLabel: resourceType === "small_variant"
              ? (isInteresting ? "Remove flag" : "Mark interesting")
              : (isInteresting ? "Exclude from report" : "Include in report"),
            flag: "interesting",
            apply: !isInteresting,
          })}
          disabled={flagMutation.isPending}
          className={`${reportButtonBase} ${isInteresting ? 'border-pass/40 bg-pass/15 text-pass' : 'border-border bg-background hover:bg-pass/10 hover:text-pass'}`}
          title={resourceType === "small_variant" ? "Toggle interesting" : isInteresting ? "Exclude from report" : "Include in report"}
        >
          {resourceType === "small_variant" ? (
            <AlertCircle className="h-3.5 w-3.5" />
          ) : (
            <FileCheck2 className="h-3.5 w-3.5" />
          )}
          {(!compact || labeledCompactReport) && (resourceType === "small_variant" ? "Interesting" : isInteresting ? "Exclude" : "Report")}
        </button>
      )}
      {supportsNoteworthy && (
        <button
          onClick={() => setPendingFlagAction({
            title: isNoteworthy ? "Remove noteworthy flag?" : "Mark finding as noteworthy?",
            description: "This changes the finding's CNV review state.",
            confirmLabel: isNoteworthy ? "Remove flag" : "Mark noteworthy",
            flag: "noteworthy",
            apply: !isNoteworthy,
          })}
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
      <ConfirmationDialog
        open={Boolean(pendingFlagAction)}
        title={pendingFlagAction?.title || "Confirm finding action"}
        description={pendingFlagAction?.description || "Confirm this clinical review change."}
        confirmLabel={pendingFlagAction?.confirmLabel || "Apply action"}
        isPending={flagMutation.isPending}
        onConfirm={confirmFlagAction}
        onCancel={() => setPendingFlagAction(null)}
      />
      <ConfirmationDialog
        open={confirmBlacklist}
        title="Add variant to center blacklist?"
        description="This creates a center-wide blacklist entry for the variant. Use a sample override only when a blacklisted finding must remain visible for a specific review."
        confirmLabel="Add to blacklist"
        isPending={blacklistMutation.isPending}
        onConfirm={() => blacklistMutation.mutateAsync().catch(() => undefined)}
        onCancel={() => setConfirmBlacklist(false)}
      />
    </div>
  )
}
