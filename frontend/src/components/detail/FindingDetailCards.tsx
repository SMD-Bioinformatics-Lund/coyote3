import { useState } from "react"
import { MessageSquare, Tags } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { TierBadge } from "@/lib/variant-ui"
import { FindingResourceType, findingQueryKeys } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { fullDateTime } from "@/lib/detail-formatters"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

function timeLabel(value: unknown) {
  return fullDateTime(value, "")
}

const tierButtonClasses: Record<number, string> = {
  1: "bg-tier1",
  2: "bg-tier2",
  3: "bg-tier3",
  4: "bg-tier4",
}

export function DetailCard({
  title,
  icon: Icon,
  tone: _tone = "border-t-panel",
  children,
}: {
  title: string
  icon: any
  tone?: string
  children: React.ReactNode
}) {
  return (
    <section className="glass-card p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary"><Icon className="h-3.5 w-3.5" /></span>
        {title}
      </h3>
      {children}
    </section>
  )
}

export function CommentsCard({ comments = [], title = "Sample Comments" }: { comments?: any[]; title?: string }) {
  return (
    <DetailCard title={title} icon={MessageSquare} tone="border-t-tier2">
      {comments.length ? (
        <div className="space-y-2">
          {comments.map((comment, index) => (
            <div key={comment._id || index} className={`rounded-lg border border-border bg-background/70 p-3 text-sm ${comment.hidden ? "opacity-50" : ""}`}>
              <div className="mb-1 flex justify-between gap-2 text-xs text-muted-foreground">
                <span className="font-bold">{comment.author || comment.user || "Unknown"}</span>
                <span>{timeLabel(comment.time_created || comment.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm">{comment.text || comment.comment || "-"}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No comments available.</p>
      )}
    </DetailCard>
  )
}

export function ClassificationsCard({
  latest,
  other = [],
  sampleId,
  resourceType,
  resourceId,
  onUpdate,
}: {
  latest?: any
  other?: any[]
  sampleId?: string
  resourceType?: FindingResourceType
  resourceId?: string
  onUpdate?: () => void
}) {
  const queryClient = useQueryClient()
  const [pendingTierAction, setPendingTierAction] = useState<{ tier: number; apply: boolean } | null>(null)
  const tierMutation = useMutation({
    mutationFn: ({ tier, apply }: { tier: number; apply: boolean }) =>
      api.patch(`/samples/${sampleId}/classifications/tier`, {
        resource_type: resourceType,
        resource_ids: resourceId ? [resourceId] : [],
        tier,
        apply,
      }),
    onSuccess: (_result, variables) => {
      if (sampleId && resourceType) {
        findingQueryKeys(sampleId, resourceType).forEach((queryKey) => {
          queryClient.invalidateQueries({ queryKey })
        })
        queryClient.invalidateQueries({
          queryKey: ["sample-comment-suggestion", sampleId],
        })
      }
      onUpdate?.()
      setPendingTierAction(null)
      notifySuccess(
        variables.apply ? "Classification updated" : "Classification removed",
        variables.apply ? `Finding classified as Tier ${variables.tier}.` : `Tier ${variables.tier} classification removed.`,
        "Classification",
      )
    },
    onError: (error) => notifyActionError("Unable to update classification", error, "Classification"),
  })
  const canMutate = Boolean(sampleId && resourceType && resourceId)
  const automaticTextWillBeGenerated = Boolean(
    pendingTierAction?.apply
      && pendingTierAction.tier === 3
      && resourceType === "small_variant",
  )

  return (
    <DetailCard title="Classifications" icon={Tags} tone="border-t-tier1">
      <div className="space-y-3">
        {canMutate && (
          <div className="rounded-lg border border-border bg-background/70 p-2">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Set tier</div>
            <div className="flex flex-wrap gap-1.5">
              {[1, 2, 3, 4].map((tier) => (
                <button
                  key={tier}
                  type="button"
                  onClick={() => setPendingTierAction({ tier, apply: true })}
                  disabled={tierMutation.isPending}
                  className={`rounded-lg px-2.5 py-1.5 text-xs font-black text-white shadow-sm disabled:opacity-50 ${tierButtonClasses[tier]}`}
                >
                  Tier {tier}
                </button>
              ))}
              {[1, 2, 3, 4].includes(Number(latest?.class || latest?.tier)) && (
                <button
                  type="button"
                  onClick={() => setPendingTierAction({
                    tier: Number(latest?.class || latest?.tier),
                    apply: false,
                  })}
                  disabled={tierMutation.isPending}
                  className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-black text-muted-foreground hover:bg-muted disabled:opacity-50"
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        )}
        {latest ? (
          <div className="rounded-lg border border-border bg-background/70 p-3">
            <div className="mb-2 flex items-center gap-2">
              <TierBadge tier={latest.class || latest.tier} />
              <span className="text-sm font-semibold">Latest classification</span>
            </div>
            <p className="text-sm text-muted-foreground">{latest.reason || latest.text || "No reason provided."}</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Not currently classified.</p>
        )}
        {other.length > 0 && (
          <div className="space-y-2">
            {other.map((item, index) => (
              <div key={item._id || index} className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2 text-xs">
                <span>{item.text || item.reason || item.variant || "Classification"}</span>
                <TierBadge tier={item.class || item.tier} />
              </div>
            ))}
          </div>
        )}
      </div>
      <ConfirmationDialog
        open={Boolean(pendingTierAction)}
        title={pendingTierAction?.apply ? `Classify finding as Tier ${pendingTierAction.tier}?` : `Remove Tier ${pendingTierAction?.tier} classification?`}
        description={pendingTierAction?.apply
          ? `This will persist a Tier ${pendingTierAction.tier} classification for the finding.${automaticTextWillBeGenerated ? " The approved Tier III annotation text will also be generated." : " No automatic annotation text is defined for this action."}`
          : "This removes the selected classification from the current assay and subpanel context."}
        confirmLabel={pendingTierAction?.apply ? "Set classification" : "Remove classification"}
        isPending={tierMutation.isPending}
        onConfirm={() => {
          if (pendingTierAction) tierMutation.mutate(pendingTierAction)
        }}
        onCancel={() => setPendingTierAction(null)}
      />
    </DetailCard>
  )
}
