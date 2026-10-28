import { AppTooltip } from "@/components/ui/app-tooltip"
import { TableBadge } from "@/components/ui/table-badge"

// CGC evidence definitions: https://pmc.ncbi.nlm.nih.gov/articles/PMC6450507/
const descriptions: Record<string, string> = {
  "1": "Strong functional and mutation evidence supports this gene's role in cancer.",
  "2": "Evidence supports this gene's role in cancer, but mutation or functional evidence is less complete than for CGC Tier 1.",
}

export function CosmicCensusTierBadge({ tier }: { tier: unknown }) {
  const value = typeof tier === "string" || typeof tier === "number" ? String(tier).trim() : ""
  if (!value) return <span className="text-muted-foreground">-</span>

  return (
    <AppTooltip
      context="COSMIC Cancer Gene Census"
      label={`CGC Tier ${value}`}
      content={`${descriptions[value] || "Tier supplied by COSMIC Cancer Gene Census."} This is gene-level evidence, not the Coyote clinical classification of this variant.`}
    >
      <TableBadge
        as="a"
        href="https://cancer.sanger.ac.uk/census"
        target="_blank"
        rel="noopener noreferrer"
        className="border-info/40 bg-info/10 text-info focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        CGC Tier {value}
      </TableBadge>
    </AppTooltip>
  )
}
