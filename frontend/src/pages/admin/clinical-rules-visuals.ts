import { cn } from "@/lib/utils"

import type { RuleStatus } from "./clinical-rules-types"

export const CLINICAL_RULE_STATUS_LABELS: Record<RuleStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  in_clinical_review: "Clinical review",
  approved: "Approved",
  rejected: "Rejected",
  published: "Published",
  retired: "Retired",
}

const STATUS_STYLES: Record<RuleStatus, string> = {
  draft: "badge-info",
  submitted: "badge-warning",
  in_clinical_review: "badge-signal",
  approved: "badge-success",
  rejected: "badge-danger",
  published: "matte-badge-production",
  retired: "border-border bg-muted text-muted-foreground",
}

export function clinicalRuleStatusStyle(status: RuleStatus) {
  return STATUS_STYLES[status]
}

const SECTION_TONES = [
  { surface: "clinical-tone-primary", rail: "clinical-tone-primary" },
  { surface: "clinical-tone-info", rail: "clinical-tone-info" },
  { surface: "clinical-tone-success", rail: "clinical-tone-success" },
  { surface: "clinical-tone-warning", rail: "clinical-tone-warning" },
] as const

export function clinicalRuleSectionTone(index: number) {
  return SECTION_TONES[index % SECTION_TONES.length]
}

export function clinicalConditionTone(type: string) {
  return cn(
    type === "predicate" && "clinical-tone-info",
    type === "all" && "clinical-tone-primary",
    type === "any" && "clinical-tone-success",
    type === "not" && "clinical-tone-danger",
    type === "collection_match" && "clinical-tone-warning",
  )
}
