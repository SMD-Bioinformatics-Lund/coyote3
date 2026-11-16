// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { createContext, useContext } from "react"

import { DEFAULT_TABLE_PAGE_SIZE } from "@/lib/defaults"

export type TablePreferences = {
  pageSize: number
  setPageSize: (pageSize: number) => void
}

export const TablePreferencesContext = createContext<TablePreferences>({
  pageSize: DEFAULT_TABLE_PAGE_SIZE,
  setPageSize: () => undefined,
})

export function useTablePreferences() {
  return useContext(TablePreferencesContext)
}
