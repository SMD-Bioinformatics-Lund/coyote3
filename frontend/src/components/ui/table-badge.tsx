import type { HTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/utils"

export const tableBadgeClassName =
  "type-badge inline-flex min-h-6 min-w-6 max-w-full shrink-0 items-center justify-center rounded-md border px-2 py-0.5 shadow-sm"

export type TableBadgeProps = HTMLAttributes<HTMLElement> & {
  as?: "span" | "a"
  children: ReactNode
  href?: string
  rel?: string
  target?: string
}

export const infoBadgeClassName =
  "h-3 min-h-3 min-w-2.5 rounded-[0.15rem] px-0.5 py-0 type-info-badge font-semibold leading-none shadow-none"

export const clinicalBadgeClassName =
  "min-h-[1.375rem] min-w-[1.375rem] px-1.5 py-0 text-xs leading-none shadow-none"

export const consequenceBadgeClassName =
  "min-h-6 min-w-6 px-2 py-0.5 type-body font-medium leading-none shadow-sm"

export const tierBadgeClassName =
  "h-[1.8125rem] min-h-[1.8125rem] min-w-[1.8125rem] rounded-full px-1.5 py-0 text-xs font-semibold leading-none shadow-sm"

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
