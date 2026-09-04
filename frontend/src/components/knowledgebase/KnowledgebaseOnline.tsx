import { ArrowRight, CheckCircle2, Database } from "lucide-react"
import { Link } from "react-router-dom"

import { buttonVariants } from "@/components/ui/button-variants"
import { databaseLogo } from "@/lib/database-logos"
import { summarizeKnowledgebaseFamilies, type KnowledgebaseStatusPayload } from "@/lib/knowledgebase-status"
import { appPath } from "@/lib/runtime-paths"
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
          const logo = databaseLogo(family.key)
          return (
            <div key={family.key} className="flex min-w-36 items-center gap-2 border-r border-border/70 pr-5 last:border-r-0">
              {logo ? (
                <img src={appPath(logo.src)} alt={logo.alt} className="h-7 w-14 shrink-0 object-contain" />
              ) : (
                <Database className="size-5 shrink-0 text-primary" aria-hidden="true" />
              )}
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 type-body-sm font-semibold text-foreground">
                  <CheckCircle2 className="size-3.5 shrink-0 text-pass" aria-label="Online" />
                  <span className="truncate">{family.family}</span>
                </p>
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
