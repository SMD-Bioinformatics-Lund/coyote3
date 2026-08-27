import { useCallback, type ReactNode } from "react"

import { TablePreferencesContext } from "@/components/data-table/table-preferences"
import { useCurrentUserAccess } from "@/lib/access-control"
import { tablePageSizeForUser, useUpdateUiSettings } from "@/lib/user-settings"

export function TablePreferencesProvider({ children }: { children: ReactNode }) {
  const accessQuery = useCurrentUserAccess()
  const updateSettings = useUpdateUiSettings()
  const pageSize = tablePageSizeForUser(accessQuery.data)
  const setPageSize = useCallback((nextPageSize: number) => {
    if (nextPageSize === pageSize) return
    updateSettings.mutate({ table_page_size: nextPageSize })
  }, [pageSize, updateSettings])

  return (
    <TablePreferencesContext.Provider value={{ pageSize, setPageSize }}>
      {children}
    </TablePreferencesContext.Provider>
  )
}
