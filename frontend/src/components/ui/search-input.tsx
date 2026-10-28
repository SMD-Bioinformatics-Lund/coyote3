import type { ComponentProps, ReactNode } from "react"
import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/** Consistent search geometry, constrained by the available toolbar or panel width. */
export function SearchInput({
  className,
  endAdornment,
  ...props
}: ComponentProps<typeof Input> & { endAdornment?: ReactNode }) {
  return (
    <div className={cn("relative w-full min-w-0 max-w-sm", className)}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        {...props}
        className={cn(
          "h-9 min-h-9 pl-9 pr-3 type-body-sm font-normal normal-case tracking-normal",
          endAdornment && "pr-10",
        )}
      />
      {endAdornment && <div className="absolute right-0 top-1/2 -translate-y-1/2">{endAdornment}</div>}
    </div>
  )
}
