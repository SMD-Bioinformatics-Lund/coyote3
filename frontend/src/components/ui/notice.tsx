// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

const tones = {
  info: "badge-info",
  success: "badge-success",
  warning: "badge-warning",
  danger: "badge-danger",
}

/** Inline feedback; callers choose live-region semantics for the operation. */
export function Notice({ tone = "info", className, ...props }: ComponentProps<"div"> & { tone?: keyof typeof tones }) {
  return <div className={cn("rounded-md border p-3 type-body-sm", tones[tone], className)} {...props} />
}
