// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { ReactNode } from "react"
import { PageFrame } from "@/components/layout/PageFrame"

export function PageShell({
  title,
  eyebrow,
  description,
  actions,
  className,
  children,
}: {
  title: string
  eyebrow?: string
  description?: string
  actions?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <PageFrame className={className}>
      <Surface variant="panel" className="page-heading responsive-card-padding text-left">
        <div className="responsive-section-gap flex flex-col md:flex-row md:items-center md:justify-between">
          <div className="min-w-0 text-left">
            {eyebrow && (
              <p className="type-page-eyebrow mb-1 text-primary">
                {eyebrow}
              </p>
            )}

            <h1 className="type-page-title text-foreground">
              {title}
            </h1>

            {description && (
              <p className="type-body mt-2 max-w-3xl text-muted-foreground">
                {description}
              </p>
            )}
          </div>

          {actions && (
            <div className="flex shrink-0 flex-wrap justify-start gap-2 md:justify-end">
              {actions}
            </div>
          )}
        </div>
      </Surface>

      {children}
    </PageFrame>
  )
}
