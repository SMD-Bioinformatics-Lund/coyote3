// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ReactNode } from "react"

export function ModuleNotice({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
      {children}
    </div>
  )
}
