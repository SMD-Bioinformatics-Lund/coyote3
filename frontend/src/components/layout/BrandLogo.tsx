// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { logo } from "@/lib/assets"
import { appPath } from "@/lib/runtime-paths"
import { cn } from "@/lib/utils"

export function BrandLogo({ className }: { className?: string }) {
  return (
    <img
      src={appPath(logo.coyote.src)}
      alt={logo.coyote.alt}
      width={711}
      height={255}
      className={cn("h-12 w-auto shrink-0 object-contain", className)}
    />
  )
}
