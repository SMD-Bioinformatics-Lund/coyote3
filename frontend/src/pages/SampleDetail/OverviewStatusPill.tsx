// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ReactNode } from "react";
import { configuredValueClasses } from "@/lib/badge-colors";
import { TableBadge } from "@/components/ui/table-badge";


export function StatusPill({ children, tone = "muted" }: { children: ReactNode; tone?: "blue" | "green" | "yellow" | "red" | "muted" }) {
  const tones = {
    blue: "badge-tone-blue",
    green: "badge-tone-green",
    yellow: "badge-tone-yellow",
    red: "badge-tone-red",
    muted: "badge-tone-muted",
  }
  const valueClass = typeof children === "string"
    ? configuredValueClasses[children.toLowerCase()]
    : undefined
  return <TableBadge className={valueClass || tones[tone]}>{children}</TableBadge>
}
