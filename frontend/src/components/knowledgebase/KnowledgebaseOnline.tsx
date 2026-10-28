import { ArrowRight, CheckCircle2 } from "lucide-react"
import { Link } from "react-router-dom"

import { buttonVariants } from "@/components/ui/button-variants"
import { DatabaseBrand } from "@/components/knowledgebase/DatabaseBrand"
import { summarizeKnowledgebaseFamilies, type KnowledgebaseStatusPayload } from "@/lib/knowledgebase-status"
import { cn } from "@/lib/utils"

export function KnowledgebaseOnline({
  payload,
  showDetailsLink = true,
}: {
  payload?: KnowledgebaseStatusPayload
  showDetailsLink?: boolean
}) {
  const families = summarizeKnowledgebaseFamilies(payload?.releases || [])

  if (!families.length) {
    return <p className="type-body-sm text-muted-foreground">No knowledgebase releases are configured.</p>
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-3">
        {families.map((family) => {
          return (
            <div key={family.key} className="content-item flex min-w-36 items-center gap-2 p-3">
              <DatabaseBrand source={family.key} label={family.family} className="type-body-sm font-semibold text-foreground" logoClassName="h-7 w-16" />
              <div className="flex min-w-0 items-center gap-1.5">
                <CheckCircle2 className="size-3.5 shrink-0 text-pass" aria-label="Online" />
                <p className="type-meta truncate text-muted-foreground" title={family.releases.join(", ")}>
                  {family.releases.join(" / ") || "Configured"}
                </p>
              </div>
            </div>
          )
        })}
      </div>
      {showDetailsLink ? (
        <Link to="/knowledgebases" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "shrink-0")}>
          Details
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      ) : null}
    </div>
  )
}
