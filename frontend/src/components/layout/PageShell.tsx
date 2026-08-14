import { ReactNode } from "react"
import { cn } from "@/lib/utils"

export function PageShell({
  title,
  eyebrow,
  description,
  actions,
  className,
  children,
}: {
  title: string
  eyebrow?: string
  description?: string
  actions?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <div className={cn("w-full max-w-[2600px] space-y-5", className)}>
      <div className="surface-panel p-5 text-left sm:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0 text-left">
            {eyebrow && <p className="type-page-eyebrow mb-1 text-primary">{eyebrow}</p>}
            <h1 className="type-page-title text-foreground">{title}</h1>
            {description && <p className="type-body mt-2 max-w-3xl text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap justify-start gap-2 md:justify-end">{actions}</div>}
        </div>
      </div>
      {children}
    </div>
  )
}
