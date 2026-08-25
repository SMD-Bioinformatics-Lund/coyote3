import { useEffect, useMemo, useState } from "react"
import type { SortingState } from "@tanstack/react-table"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { useTablePreferences } from "@/components/data-table/table-preferences"

export const CLINICAL_TABLE_STALE_MS = 2 * 60 * 1000
export const CLINICAL_TABLE_CACHE_MS = 15 * 60 * 1000

type UseClinicalTableStateOptions = {
  prefix: string
  tab?: string
  defaultPage?: number
  defaultPerPage?: number
  searchDebounceMs?: number
}

export function useClinicalTableState({
  searchDebounceMs = 250,
  ...options
}: UseClinicalTableStateOptions) {
  const { pageSize } = useTablePreferences()
  const tableState = useUrlTableState({
    ...options,
    defaultPerPage: options.defaultPerPage ?? pageSize,
  })
  const [debouncedSearchText, setDebouncedSearchText] = useState("")

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearchText(tableState.searchText.trim())
    }, searchDebounceMs)
    return () => window.clearTimeout(timeout)
  }, [searchDebounceMs, tableState.searchText])

  const tableProps = useMemo(() => ({
    sortingState: tableState.sorting,
    manualSorting: true,
    searchValue: tableState.searchText,
    onPageChange: (page: number) => {
      tableState.setPage(page)
      tableState.updateTableSearchParams({ page })
    },
    onPerPageChange: (perPage: number) => {
      tableState.setPerPage(perPage)
      tableState.setPage(1)
      tableState.updateTableSearchParams({ perPage, page: 1 })
    },
    onSortingChange: (sorting: SortingState) => {
      tableState.setSorting(sorting)
      tableState.setPage(1)
      tableState.updateTableSearchParams({ sorting, page: 1 })
    },
    onSearchChange: (search: string) => {
      tableState.setSearchText(search)
      tableState.setPage(1)
      tableState.updateTableSearchParams({ search, page: 1 })
    },
  }), [tableState])

  return {
    ...tableState,
    debouncedSearchText,
    queryKeyState: [
      tableState.page,
      tableState.perPage,
      debouncedSearchText,
      tableState.sortParam,
    ] as const,
    tableProps,
  }
}
