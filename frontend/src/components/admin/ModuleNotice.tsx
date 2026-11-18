// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Notice } from "@/components/ui/notice"
import type { ReactNode } from "react"

export function ModuleNotice({ children }: { children: ReactNode }) {
  return (
    <Notice tone="warning">
      {children}
    </Notice>
  )
}
