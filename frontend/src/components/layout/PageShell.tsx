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
            {eyebrow && <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p>}
            <h1 className="text-2xl font-semibold leading-tight tracking-normal text-foreground sm:text-[1.7rem]">{title}</h1>
            {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap justify-start gap-2 md:justify-end">{actions}</div>}
        </div>
      </div>
      {children}
    </div>
  )
}
