import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  applyFindingAction,
  FindingAction,
  FindingResourceType,
  findingQueryKeys,
  setSingleFlag,
} from "@/lib/finding-actions"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

export function useBulkFindingAction(sampleId: string, resourceType: FindingResourceType) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ action, resourceIds }: { action: FindingAction; resourceIds: string[] }) =>
      applyFindingAction({ sampleId, resourceType, action, resourceIds }),
    onSuccess: (_result, variables) => {
      findingQueryKeys(sampleId, resourceType).forEach((queryKey) => {
        queryClient.invalidateQueries({ queryKey })
      })
      queryClient.invalidateQueries({ queryKey: ["sample-comment-suggestion", sampleId] })
      notifySuccess(
        "Finding action applied",
        `${variables.action} was applied to ${variables.resourceIds.length} selected item(s).`,
        resourceType
      )
    },
    onError: (error) => {
      notifyActionError("Unable to apply finding action", error, resourceType)
    },
  })
}

export function useSingleFindingFlag(sampleId: string, resourceType: FindingResourceType) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      resourceId,
      flag,
      apply,
    }: {
      resourceId: string
      flag: "false-positive" | "irrelevant" | "interesting" | "noteworthy" | "override-blacklist"
      apply: boolean
    }) => setSingleFlag({ sampleId, resourceType, resourceId, flag, apply }),
    onSuccess: (_result, variables) => {
      findingQueryKeys(sampleId, resourceType).forEach((queryKey) => {
        queryClient.invalidateQueries({ queryKey })
      })
      queryClient.invalidateQueries({ queryKey: ["sample-comment-suggestion", sampleId] })
      notifySuccess(
        variables.apply ? "Flag applied" : "Flag removed",
        `${variables.flag} was ${variables.apply ? "applied" : "removed"}.`,
        resourceType
      )
    },
    onError: (error) => {
      notifyActionError("Unable to update flag", error, resourceType)
    },
  })
}
