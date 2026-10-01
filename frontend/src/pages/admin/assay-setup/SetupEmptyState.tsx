import type { LucideIcon } from "lucide-react"

export function SetupEmptyState({ icon: Icon, title, description }: {
  icon: LucideIcon
  title: string
  description?: string
}) {
  return (
    <div role="status" className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-center">
      <Icon aria-hidden="true" className="size-6 text-primary" />
      <p className="type-body font-medium">{title}</p>
      {description && <p className="type-body max-w-lg text-muted-foreground">{description}</p>}
    </div>
  )
}
