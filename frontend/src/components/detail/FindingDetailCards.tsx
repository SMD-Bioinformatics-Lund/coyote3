import { useState } from "react"
import { CircleHelp, MessageSquare, Tags } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { TierBadge } from "@/lib/variant-ui"
import { FindingResourceType, findingQueryKeys } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { CommentCard } from "@/components/comments/CommentCard"
import { DetailCard } from "@/components/detail/FindingDetailLayout"

const tierButtonClasses: Record<number, string> = {
  1: "bg-tier1",
  2: "bg-tier2",
  3: "bg-tier3",
  4: "bg-tier4",
}

export function CommentsCard({ comments = [], title = "Sample Comments" }: { comments?: any[]; title?: string }) {
  const visibleComments = comments.filter((comment) => !comment?.hidden)
  return (
    <DetailCard title={title} icon={MessageSquare}>
      {visibleComments.length ? (
        <div className="space-y-2">
          {visibleComments.map((comment, index) => (
            <CommentCard key={comment._id || index} comment={comment} dateDisplay="full" allowHide={false} />
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
  const controlsQuery = useApplicationModules()
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
  const canMutate = Boolean(
    sampleId
      && resourceType
      && resourceId
      && tieringIsEnabled(controlsQuery.data, resourceType),
  )
  return (
    <DetailCard title="Classifications" icon={Tags}>
      <div className="space-y-3">
        {canMutate && (
          <div className="rounded-lg border border-border bg-background/70 p-2">
            <div className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Set tier</div>
            <div className="flex flex-wrap gap-1.5">
              {[1, 2, 3, 4].map((tier) => (
                <button
                  key={tier}
                  type="button"
                  onClick={() => setPendingTierAction({ tier, apply: true })}
                  disabled={tierMutation.isPending}
                  className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm disabled:opacity-50 ${tierButtonClasses[tier]}`}
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
                  className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-muted disabled:opacity-50"
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        )}
        {latest && Number(latest.class ?? latest.tier) !== 999 ? (
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
                <div>
                  <span>{item.text || item.reason || item.variant || "Classification"}</span>
                  <div className="type-meta text-muted-foreground">{[item.asp_group, item.asp_id, item.diagnosis_id, item.namespace].filter(Boolean).join(" · ")}</div>
                  {item.match_level === "parent_group" && <div className="type-meta text-muted-foreground">Inherited from parent group · confirmation required</div>}
                </div>
                <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-muted-foreground">
                  {item.match_level === "same_assay" ? <TierBadge tier={item.class || item.tier} /> : <>Tier {item.class || item.tier}</>}
                  <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
                  Re-tier required
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
      <ConfirmationDialog
        open={Boolean(pendingTierAction)}
        title={pendingTierAction?.apply ? `Classify finding as Tier ${pendingTierAction.tier}?` : `Remove Tier ${pendingTierAction?.tier} classification?`}
        description={pendingTierAction?.apply
          ? `This will persist a Tier ${pendingTierAction.tier} classification for the finding.`
          : "This removes the selected classification from the current assay and diagnosis context."}
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
