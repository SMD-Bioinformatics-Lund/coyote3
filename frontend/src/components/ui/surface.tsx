// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

const surfaces = {
  panel: "surface-panel",
  card: "glass-card",
  inset: "paper-inset rounded-md",
}

/** Shared surface treatment; callers own content layout and padding. */
export function Surface({
  as: Component = "div",
  variant = "card",
  className,
  ...props
}: ComponentProps<"div"> & {
  as?: "div" | "section" | "article"
  variant?: keyof typeof surfaces
}) {
  return <Component className={cn(surfaces[variant], className)} {...props} />
}
