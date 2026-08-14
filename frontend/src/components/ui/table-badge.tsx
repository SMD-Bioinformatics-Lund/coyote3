import type { HTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/utils"

export const tableBadgeClassName =
  "type-badge inline-flex min-h-5 min-w-5 max-w-full shrink-0 items-center justify-center rounded-md border px-2 py-0.5 shadow-sm"

export type TableBadgeProps = HTMLAttributes<HTMLElement> & {
  as?: "span" | "a"
  children: ReactNode
  href?: string
  rel?: string
  target?: string
}

export const infoBadgeClassName =
  "h-[1.125rem] min-h-[1.125rem] min-w-4 rounded px-1.5 py-0 text-[0.625rem] font-semibold leading-none shadow-none"

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

/** Extra-compact marker used in the INFO column of clinical finding tables. */
export function InfoBadge({ className, ...props }: TableBadgeProps) {
  return <TableBadge className={cn(infoBadgeClassName, className)} {...props} />
}
