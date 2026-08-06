import type { HTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/utils"

export const tableBadgeClassName =
  "inline-flex min-h-5 min-w-5 max-w-full shrink-0 items-center justify-center rounded-md border px-2 py-0.5 text-[0.68rem] font-bold leading-none shadow-sm"

type TableBadgeProps = HTMLAttributes<HTMLElement> & {
  as?: "span" | "a"
  children: ReactNode
  href?: string
  rel?: string
  target?: string
}

/** Compact badge geometry shared by clinical and administrative data tables. */
export function TableBadge({
  as = "span",
  children,
  className,
  ...props
}: TableBadgeProps) {
  const Component = as

  return (
    <Component
      data-slot="table-badge"
      className={cn(tableBadgeClassName, className)}
      {...props}
    >
      {children}
    </Component>
  )
}
