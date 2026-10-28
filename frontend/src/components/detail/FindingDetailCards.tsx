import { useState } from "react"
import { icon } from "@/lib/assets"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { TierBadge } from "@/lib/variant-ui"
import { FindingResourceType, findingQueryKeys } from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { tieringIsEnabled, useApplicationModules } from "@/lib/app-module-state"
import { CommentCard } from "@/components/comments/CommentCard"
import { DetailCard } from "@/components/detail/FindingDetailLayout"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { TimeDisplay } from "@/components/ui/time-display"
import { MarkdownText } from "@/components/comments/MarkdownText"

interface ClassificationVersion {
  _id?: string
  class?: number
  tier?: number
  reason?: string
  text?: string
  author?: string
  time_created?: string
  is_active?: boolean
  historical_sample_match?: boolean
  legacy_fallback?: boolean
  history?: ClassificationVersion[]
}

const tierButtonClasses: Record<number, string> = {
  1: "bg-tier1",
  2: "bg-tier2",
  3: "bg-tier3",
  4: "bg-tier4",
}

export function CommentsCard({ comments = [], title = "Sample Comments" }: { comments?: any[]; title?: string }) {
  const visibleComments = comments.filter((comment) => !comment?.hidden)
  return (
    <DetailCard title={title} icon={icon.messageSquare}>
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
  unavailableReason,
  onUpdate,
}: {
  latest?: ClassificationVersion
  other?: any[]
  sampleId?: string
  resourceType?: FindingResourceType
  resourceId?: string
  unavailableReason?: string
  onUpdate?: () => void
}) {
  const queryClient = useQueryClient()
  const controlsQuery = useApplicationModules()
  const access = useCurrentUserAccess()
  const currentTier = Number(latest?.class ?? latest?.tier)
  const history = latest?.history || []
  const [pendingTierAction, setPendingTierAction] = useState<{
    tier: number; apply: boolean; deactivation_scope?: "group"
  } | null>(null)
  const tierMutation = useMutation({
    mutationFn: ({ tier, apply, deactivation_scope }: {
      tier: number; apply: boolean; deactivation_scope?: "group"
    }) =>
      api.patch(`/samples/${sampleId}/classifications/tier`, {
        resource_type: resourceType,
        resource_ids: resourceId ? [resourceId] : [],
        tier,
        apply,
        ...(deactivation_scope ? { deactivation_scope } : {}),
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
      queryClient.invalidateQueries({ queryKey: ["tiered-variant-search"] })
      queryClient.invalidateQueries({ queryKey: ["tiered-variant-context"] })
      setPendingTierAction(null)
      notifySuccess(
        variables.apply ? "Classification updated" : "Annotations deactivated",
        variables.apply ? `Finding classified as Tier ${variables.tier}.`
          : variables.deactivation_scope === "group"
            ? "Finding annotations deactivated across the biological group. History is retained."
            : `Tier ${variables.tier} classification deactivated. History is retained.`,
        "Classification",
      )
    },
    onError: (error) => notifyActionError("Unable to update classification", error, "Classification"),
  })
  const canMutate = Boolean(
    sampleId
      && resourceType
      && resourceId
      && !unavailableReason
      && tieringIsEnabled(controlsQuery.data, resourceType),
  )
  return (
    <DetailCard title="Classifications" icon={icon.tags}>
      <div className="space-y-3">
        {canMutate && (
          <div className="rounded-lg border border-border bg-background/70 p-2">
            <div className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Set tier</div>
            <div className="flex flex-wrap gap-1.5">
              {[1, 2, 3, 4].map((tier) => (
                <button
                  key={tier}
                  type="button"
                  aria-pressed={currentTier === tier}
                  onClick={() => setPendingTierAction({ tier, apply: true })}
                  disabled={tierMutation.isPending}
                  className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 ${tierButtonClasses[tier]} ${currentTier === tier ? "opacity-100" : "opacity-65 hover:opacity-100 focus-visible:opacity-100"}`}
                >
                  Tier {tier}
                </button>
              ))}
              {latest?.is_active !== false && [1, 2, 3, 4].includes(Number(latest?.class || latest?.tier)) && (
                <button
                  type="button"
                  onClick={() => setPendingTierAction({
                    tier: Number(latest?.class || latest?.tier),
                    apply: false,
                  })}
                  disabled={tierMutation.isPending}
                  className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-muted disabled:opacity-50"
                >
                  Deactivate
                </button>
              )}
              {hasPermission(access.data, "tier:remove:global") && (
                <button
                  type="button"
                  onClick={() => setPendingTierAction({
                    tier: [1, 2, 3, 4].includes(Number(latest?.class || latest?.tier))
                      ? Number(latest?.class || latest?.tier) : 3,
                    apply: false, deactivation_scope: "group",
                  })}
                  disabled={tierMutation.isPending}
                  className="rounded-lg border border-warn/50 bg-warn/10 px-2.5 py-1.5 text-xs font-semibold text-warn hover:bg-warn/20 disabled:opacity-50"
                >Deactivate group annotations</button>
              )}
            </div>
          </div>
        )}
        {latest && Number(latest.class ?? latest.tier) !== 999 ? (
          <div className="rounded-lg border border-border bg-background/70 p-3">
            <div className="mb-2 flex items-center gap-2">
              <TierBadge tier={latest.class || latest.tier} />
              <span className="text-sm font-semibold">Latest classification</span>
              {latest.is_active === false && <span className="type-label text-warn">Inactive</span>}
            </div>
            <p className="text-sm text-muted-foreground">{latest.reason || latest.text || "No reason provided."}</p>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 type-meta text-muted-foreground">
              <span>{latest.author || "Unknown author"}</span>
              <TimeDisplay value={latest.time_created} mode="full" fallback="Time not recorded" />
            </div>
            {latest.historical_sample_match && (
              <p className="mt-2 type-caption text-muted-foreground">Historical annotation linked to this sample. It is inactive for reuse on other samples.</p>
            )}
            {latest.legacy_fallback && (
              <p className="mt-2 type-caption text-warn">Legacy fallback: this is the latest matching annotation, including inactive records. No saved sample link confirms which tier was used. Re-tier before reporting.</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{unavailableReason || "Not currently classified."}</p>
        )}
        {history.length > 0 && (
          <section aria-label="Classification history" className="space-y-2">
            <h3 className="type-label font-semibold text-muted-foreground">Classification history</h3>
            {history.map((item) => (
              <article key={item._id} className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <TierBadge tier={item.class ?? item.tier} />
                  {item.is_active === false && <span className="type-label text-warn">Inactive</span>}
                  <span className="type-meta text-muted-foreground">{item.author || "Unknown author"}</span>
                  <TimeDisplay value={item.time_created} mode="full" fallback="Time not recorded" className="type-meta text-muted-foreground" />
                </div>
                <MarkdownText text={item.text || item.reason || "No reason provided."} />
              </article>
            ))}
          </section>
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
                  <icon.circleHelp className="h-3.5 w-3.5" aria-hidden="true" />
                  Re-tier required
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
      <ConfirmationDialog
        open={Boolean(pendingTierAction)}
        title={pendingTierAction?.apply ? `Classify finding as Tier ${pendingTierAction.tier}?`
          : pendingTierAction?.deactivation_scope === "group" ? "Deactivate group annotations?"
            : `Deactivate Tier ${pendingTierAction?.tier} classification?`}
        description={pendingTierAction?.apply
          ? `This will persist a Tier ${pendingTierAction.tier} classification for the finding.`
          : pendingTierAction?.deactivation_scope === "group"
            ? "This deactivates all annotations for this finding across every assay and diagnosis in the biological group, within the current namespace. Annotation records and sample/report history are retained."
            : "This deactivates the selected tier in the current assay and diagnosis context. Annotation records and sample/report history are retained."}
        confirmLabel={pendingTierAction?.apply ? "Set classification" : "Deactivate annotations"}
        isPending={tierMutation.isPending}
        onConfirm={() => {
          if (pendingTierAction) tierMutation.mutate(pendingTierAction)
        }}
        onCancel={() => setPendingTierAction(null)}
      />
    </DetailCard>
  )
}
