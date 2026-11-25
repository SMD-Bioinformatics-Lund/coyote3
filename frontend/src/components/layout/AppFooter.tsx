// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { runtimeConfig } from "@/lib/runtime-config"

export function AppFooter() {
  return (
    <footer
      aria-label="Application footer"
      className="app-footer relative z-20 flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-0.5 py-1 text-xs leading-4 text-muted-foreground"
    >
      <span>© {new Date().getFullYear()} Section for Molecular Diagnostics (SMD), Lund · Coyote4 v{runtimeConfig.appVersion}</span>
      <span className="sm:ml-auto sm:text-right">For research use only. Not for clinical or diagnostic use.</span>
    </footer>
  )
}
