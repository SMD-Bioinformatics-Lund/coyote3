// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

export type TableDensity = "compact" | "standard" | "relaxed"

/** Native table semantics shared by static tables and the sortable DataTable. */
export function Table({ className, density = "standard", ...props }: ComponentProps<"table"> & { density?: TableDensity }) {
  return <table data-density={density} className={cn("ui-table type-table-cell", className)} {...props} />
}

export function TableHeader({ className, ...props }: ComponentProps<"thead">) {
  return <thead className={cn("ui-table-header type-table-header", className)} {...props} />
}

export function TableBody({ className, ...props }: ComponentProps<"tbody">) {
  return <tbody className={cn("ui-table-body", className)} {...props} />
}

export function TableRow({ className, ...props }: ComponentProps<"tr">) {
  return <tr className={cn("ui-table-row", className)} {...props} />
}

export function TableHead({ className, scope = "col", ...props }: ComponentProps<"th">) {
  return <th scope={scope} className={cn("ui-table-head", className)} {...props} />
}

export function TableCell({ className, ...props }: ComponentProps<"td">) {
  return <td className={cn("ui-table-cell", className)} {...props} />
}
