// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { runtimeConfig } from "@/lib/runtime-config"

export function AppFooter() {
  return (
    <footer
      aria-label="Application footer"
      className="relative z-10 flex shrink-0 flex-col gap-2 border-t border-border/60 py-3 text-xs leading-relaxed text-muted-foreground sm:flex-row sm:items-start sm:justify-between"
    >
      <span>© {new Date().getFullYear()} Sektion för molekylär diagnostik (SMD), Lund · Coyote4 v{runtimeConfig.appVersion}</span>
      <span className="sm:text-right">For research use only. Not for clinical or diagnostic use.</span>
    </footer>
  )
}
