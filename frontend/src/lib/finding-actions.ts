import { api } from "@/lib/api"

export type FindingResourceType = "small_variant" | "cnv" | "fusion" | "translocation"

export type FindingAction =
  | "tier_1"
  | "tier_2"
  | "tier_3"
  | "tier_4"
  | "remove_tier_1"
  | "remove_tier_2"
  | "remove_tier_3"
  | "remove_tier_4"
  | "fp"
  | "unfp"
  | "irrelevant"
  | "relevant"
  | "interesting"
  | "uninteresting"
  | "noteworthy"
  | "unnoteworthy"
  | "blacklist"
  | "blacklisted"
  | "unblacklisted"
  | "override_blacklist"
  | "clear_override_blacklist"

export type FindingActionOption = {
  value: FindingAction
  label: string
}

const FINDING_ACTION_LABELS: Record<FindingAction, string> = {
  tier_1: "Classify as Tier 1",
  tier_2: "Classify as Tier 2",
  tier_3: "Classify as Tier 3",
  tier_4: "Classify as Tier 4",
  remove_tier_1: "Remove Tier 1",
  remove_tier_2: "Remove Tier 2",
  remove_tier_3: "Remove Tier 3",
  remove_tier_4: "Remove Tier 4",
  fp: "Mark False Positive",
  unfp: "Unmark False Positive",
  irrelevant: "Mark Irrelevant",
  relevant: "Unmark Irrelevant",
  interesting: "Mark Interesting",
  uninteresting: "Unmark Interesting",
  noteworthy: "Mark Noteworthy",
  unnoteworthy: "Unmark Noteworthy",
  blacklist: "Add to Blacklist",
  blacklisted: "Mark Blacklisted",
  unblacklisted: "Remove Blacklist",
  override_blacklist: "Override Blacklist",
  clear_override_blacklist: "Clear Blacklist Override",
}

const TIER_ACTIONS: FindingAction[] = [
  "tier_1",
  "tier_2",
  "tier_3",
  "tier_4",
  "remove_tier_1",
  "remove_tier_2",
  "remove_tier_3",
  "remove_tier_4",
]

const REVIEW_ACTIONS: FindingAction[] = [
  "fp",
  "unfp",
  "irrelevant",
  "relevant",
  "interesting",
  "uninteresting",
]

const FINDING_BULK_ACTIONS: Record<FindingResourceType, FindingAction[]> = {
  small_variant: [
    ...TIER_ACTIONS,
    ...REVIEW_ACTIONS,
    "blacklist",
    "override_blacklist",
    "clear_override_blacklist",
  ],
  cnv: ["fp", "unfp", "interesting", "uninteresting", "noteworthy", "unnoteworthy"],
  fusion: [...TIER_ACTIONS, ...REVIEW_ACTIONS, "blacklisted", "unblacklisted"],
  translocation: ["fp", "unfp", "interesting", "uninteresting"],
}

const RESOURCE_ACTION_LABELS: Partial<
  Record<FindingResourceType, Partial<Record<FindingAction, string>>>
> = {
  cnv: {
    interesting: "Include in report",
    uninteresting: "Exclude from report",
  },
  translocation: {
    interesting: "Include in report",
    uninteresting: "Exclude from report",
  },
}

export function findingBulkActionOptions(resourceType: FindingResourceType): FindingActionOption[] {
  const resourceLabels = RESOURCE_ACTION_LABELS[resourceType] || {}
  return FINDING_BULK_ACTIONS[resourceType].map((value) => ({
    value,
    label: resourceLabels[value] || FINDING_ACTION_LABELS[value],
  }))
}

const listPathByResource: Record<FindingResourceType, string> = {
  small_variant: "small-variants",
  cnv: "cnvs",
  fusion: "fusions",
  translocation: "translocations",
}

const idParamByResource: Record<FindingResourceType, string> = {
  small_variant: "resource_ids",
  cnv: "resource_ids",
  fusion: "fusion_ids",
  translocation: "resource_ids",
}

function queryList(name: string, values: string[]) {
  const params = new URLSearchParams()
  values.forEach((value) => params.append(name, value))
  return params.toString()
}

export function findingQueryKeys(sampleId: string, resourceType: FindingResourceType) {
  const keys: unknown[][] = [["sample", sampleId]]
  if (resourceType === "small_variant") keys.push(["sample-variants", sampleId], ["variants", sampleId])
  if (resourceType === "cnv") keys.push(["sample-cnvs", sampleId], ["cnvs", sampleId])
  if (resourceType === "fusion") keys.push(["sample-fusions", sampleId], ["fusions", sampleId])
  if (resourceType === "translocation") {
    keys.push(["sample-translocations", sampleId], ["translocations", sampleId])
  }
  return keys
}

async function setTierBulk({
  sampleId,
  resourceType,
  resourceIds,
  tier,
  apply,
}: {
  sampleId: string
  resourceType: FindingResourceType
  resourceIds: string[]
  tier: number
  apply: boolean
}) {
  return api.patch(`/samples/${sampleId}/classifications/tier`, {
    resource_type: resourceType,
    resource_ids: resourceIds,
    tier,
    apply,
  })
}

async function setBulkFlag({
  sampleId,
  resourceType,
  resourceIds,
  flag,
  apply,
}: {
  sampleId: string
  resourceType: FindingResourceType
  resourceIds: string[]
  flag: "false-positive" | "irrelevant" | "blacklisted"
  apply: boolean
}) {
  const listPath = listPathByResource[resourceType]

  if (resourceType === "small_variant") {
    return api.patch(`/samples/${sampleId}/${listPath}/flags/${flag}`, {
      resource_ids: resourceIds,
      apply,
    })
  }

  if (resourceType === "fusion") {
    const query = queryList(idParamByResource[resourceType], resourceIds)
    return api.patch(`/samples/${sampleId}/${listPath}/flags/${flag}?apply=${apply}&${query}`)
  }

  return Promise.all(
    resourceIds.map((resourceId) =>
      setSingleFlag({ sampleId, resourceType, resourceId, flag, apply }),
    ),
  )
}

export async function setSingleFlag({
  sampleId,
  resourceType,
  resourceId,
  flag,
  apply,
}: {
  sampleId: string
  resourceType: FindingResourceType
  resourceId: string
  flag: "false-positive" | "irrelevant" | "interesting" | "noteworthy" | "override-blacklist" | "blacklisted"
  apply: boolean
}) {
  const listPath = listPathByResource[resourceType]
  const method = apply ? api.patch : api.delete
  return method(`/samples/${sampleId}/${listPath}/${resourceId}/flags/${flag}`)
}

export async function applyFindingAction({
  sampleId,
  resourceType,
  action,
  resourceIds,
}: {
  sampleId: string
  resourceType: FindingResourceType
  action: FindingAction
  resourceIds: string[]
}) {
  const ids = resourceIds.filter(Boolean)
  if (ids.length === 0) return

  const tierMatch = action.match(/^(remove_)?tier_(\d)$/)
  if (tierMatch) {
    return setTierBulk({
      sampleId,
      resourceType,
      resourceIds: ids,
      tier: Number(tierMatch[2]),
      apply: !tierMatch[1],
    })
  }

  if (action === "fp" || action === "unfp") {
    return setBulkFlag({
      sampleId,
      resourceType,
      resourceIds: ids,
      flag: "false-positive",
      apply: action === "fp",
    })
  }

  if (action === "irrelevant" || action === "relevant") {
    return setBulkFlag({
      sampleId,
      resourceType,
      resourceIds: ids,
      flag: "irrelevant",
      apply: action === "irrelevant",
    })
  }

  if (action === "blacklisted" || action === "unblacklisted") {
    return setBulkFlag({
      sampleId,
      resourceType,
      resourceIds: ids,
      flag: "blacklisted",
      apply: action === "blacklisted",
    })
  }

  if (action === "interesting" || action === "uninteresting") {
    return Promise.all(
      ids.map((resourceId) =>
        setSingleFlag({
          sampleId,
          resourceType,
          resourceId,
          flag: "interesting",
          apply: action === "interesting",
        }),
      ),
    )
  }

  if (action === "noteworthy" || action === "unnoteworthy") {
    return Promise.all(
      ids.map((resourceId) =>
        setSingleFlag({
          sampleId,
          resourceType,
          resourceId,
          flag: "noteworthy",
          apply: action === "noteworthy",
        }),
      ),
    )
  }

  if (action === "blacklist") {
    return Promise.all(
      ids.map((resourceId) =>
        api.post(`/samples/${sampleId}/small-variants/${resourceId}/blacklist-entries`, {}),
      ),
    )
  }

  if (action === "override_blacklist" || action === "clear_override_blacklist") {
    return Promise.all(
      ids.map((resourceId) =>
        setSingleFlag({
          sampleId,
          resourceType,
          resourceId,
          flag: "override-blacklist",
          apply: action === "override_blacklist",
        }),
      ),
    )
  }
}
