import { Badge } from "@/components/ui/badge"

import type { RuleStatus } from "./clinical-rules-types"
import {
  CLINICAL_RULE_STATUS_LABELS,
  clinicalRuleStatusStyle,
} from "./clinical-rules-visuals"

export function ClinicalRuleStatusBadge({ status, prefix }: { status: RuleStatus; prefix?: string }) {
  return <Badge variant="outline" className={clinicalRuleStatusStyle(status)}>{prefix}{CLINICAL_RULE_STATUS_LABELS[status]}</Badge>
}
