// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export function PageFrame({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "page-shell-fluid responsive-page-padding responsive-section-gap flex w-full flex-col 3xl:mx-auto 3xl:content-ultrawide",
        className,
      )}
    >
      {children}
    </div>
  )
}
