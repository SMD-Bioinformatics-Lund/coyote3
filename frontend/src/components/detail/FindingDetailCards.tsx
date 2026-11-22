// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Badge } from "@/components/ui/badge"
import { Surface } from "@/components/ui/surface"
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
  const currentTier = Number(latest?.class ?? latest?.tier)
  const history = latest?.history || []
  const [pendingTierAction, setPendingTierAction] = useState<{
    tier: number; apply: true
  } | null>(null)
  const tierMutation = useMutation({
    mutationFn: ({ tier, apply }: {
      tier: number; apply: true
    }) =>
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
      queryClient.invalidateQueries({ queryKey: ["tiered-variant-search"] })
      queryClient.invalidateQueries({ queryKey: ["tiered-variant-context"] })
      setPendingTierAction(null)
      notifySuccess(
        "Classification created",
        `Finding classified as Tier ${variables.tier}.`,
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
          <Surface variant="inset" className="p-2">
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
            </div>
          </Surface>
        )}
        {latest && Number(latest.class ?? latest.tier) !== 999 ? (
          <Surface variant="inset" className="p-3">
            <div className="mb-2 flex items-center gap-2">
              <TierBadge tier={latest.class || latest.tier} />
              <span className="text-sm font-semibold">Latest classification</span>
            </div>
            <p className="text-sm text-muted-foreground">{latest.reason || latest.text || "No reason provided."}</p>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 type-meta text-muted-foreground">
              <span>{latest.author || "Unknown author"}</span>
              <TimeDisplay value={latest.time_created} mode="full" fallback="Time not recorded" />
            </div>
          </Surface>
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
                <Badge variant="outline" className="inline-flex items-center gap-1 border-border bg-muted text-muted-foreground">
                  {item.match_level === "same_assay" ? <TierBadge tier={item.class || item.tier} /> : <>Tier {item.class || item.tier}</>}
                  <icon.circleHelp className="h-3.5 w-3.5" aria-hidden="true" />
                  Re-tier required
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>
      <ConfirmationDialog
        open={Boolean(pendingTierAction)}
        title={`Classify finding as Tier ${pendingTierAction?.tier}?`}
        description={`This creates a new Tier ${pendingTierAction?.tier} annotation. Existing annotations are retained.`}
        confirmLabel="Set classification"
        isPending={tierMutation.isPending}
        onConfirm={() => {
          if (pendingTierAction) tierMutation.mutate(pendingTierAction)
        }}
        onCancel={() => setPendingTierAction(null)}
      />
    </DetailCard>
  )
}
