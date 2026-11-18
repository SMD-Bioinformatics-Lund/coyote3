// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { logo } from "@/lib/assets"
import { appPath } from "@/lib/runtime-paths"
import { cn } from "@/lib/utils"

/** Decorative spinner; its surrounding status or button supplies the operation label. */
export function LoadingIndicator({ className }: { className?: string }) {
  return <img
    src={appPath(logo.coyoteEmblem.src)}
    alt=""
    aria-hidden="true"
    width={64}
    height={64}
    className={cn("coyote-spinner size-4 shrink-0 object-contain", className)}
  />
}
