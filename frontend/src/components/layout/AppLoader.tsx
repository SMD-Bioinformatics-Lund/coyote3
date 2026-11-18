// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { LoadingIndicator } from "@/components/ui/loading-indicator"

export function AppLoader({ label = "Loading" }: { label?: string }) {
  return <GlobalLoadingIndicator label={label} />
}

export function GlobalLoadingIndicator({ label = "Loading" }: { label?: string }) {
  return (
    <div className="global-loader" role="status" aria-live="polite" aria-label={label}>
      <LoadingIndicator className="size-14" />
      <span className="sr-only">{label}</span>
    </div>
  )
}
