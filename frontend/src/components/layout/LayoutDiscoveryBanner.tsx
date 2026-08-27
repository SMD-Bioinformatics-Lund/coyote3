import { Columns3, Rows3 } from "lucide-react"

import { Button } from "@/components/ui/button"

type LayoutDiscoveryBannerProps = {
  onTryModern: () => void
}

export function LayoutDiscoveryBanner({ onTryModern }: LayoutDiscoveryBannerProps) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-sm text-card-foreground shadow-[0_2px_8px_var(--paper-shadow)]"
      role="status"
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <Rows3 className="h-4 w-4" />
        </span>
        <div>
          <p className="font-semibold text-foreground">Try the modern layout</p>
          <p className="text-muted-foreground">Modern presents one section at a time using tabs.</p>
        </div>
      </div>
      <Button type="button" size="sm" onClick={onTryModern}>
        <Columns3 className="h-4 w-4" />
        Try modern
      </Button>
    </div>
  )
}
