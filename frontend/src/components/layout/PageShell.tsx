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
    <div className={cn("w-full max-w-[2600px] space-y-3", className)}>
      <div className="surface-panel p-3 text-left">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0 text-left">
            {eyebrow && <p className="text-xs font-bold uppercase tracking-wider text-primary">{eyebrow}</p>}
            <h1 className="text-2xl font-black tracking-tight text-foreground">{title}</h1>
            {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap justify-start gap-2 md:justify-end">{actions}</div>}
        </div>
      </div>
      {children}
    </div>
  )
}
