import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import type { SortingState } from "@tanstack/react-table"

export type UrlTableState = {
  page: number
  perPage: number
  searchText: string
  sorting: SortingState
  activeSort: SortingState[number] | undefined
  sortParam: string
  setPage: (page: number) => void
  setPerPage: (perPage: number) => void
  setSearchText: (searchText: string) => void
  setSorting: (sorting: SortingState) => void
  updateTableSearchParams: (next: {
    page?: number
    perPage?: number
    search?: string
    sorting?: SortingState
  }) => void
}

type UseUrlTableStateOptions = {
  prefix: string
  tab?: string
  defaultPage?: number
  defaultPerPage?: number
}

function positiveIntParam(value: string | null, fallback: number) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function sortingFromParam(value: string | null): SortingState {
  if (!value) return []
  return value
    .split(",")
    .map((part) => {
      const [id, direction] = part.split(":")
      const cleanId = id?.trim()
      if (!cleanId) return null
      return { id: cleanId, desc: direction === "desc" }
    })
    .filter(Boolean) as SortingState
}

function sortingToParam(sorting: SortingState) {
  return sorting
    .filter((item) => item.id)
    .map((item) => `${item.id}:${item.desc ? "desc" : "asc"}`)
    .join(",")
}

export function useUrlTableState({
  prefix,
  tab,
  defaultPage = 1,
  defaultPerPage = 50,
}: UseUrlTableStateOptions): UrlTableState {
  const [searchParams, setSearchParams] = useSearchParams()
  const pageKey = `${prefix}_page`
  const perPageKey = `${prefix}_per_page`
  const searchKey = `${prefix}_q`
  const sortKey = `${prefix}_sort`

  const [page, setPage] = useState(() => positiveIntParam(searchParams.get(pageKey), defaultPage))
  const [perPage, setPerPage] = useState(() => positiveIntParam(searchParams.get(perPageKey), defaultPerPage))
  const [searchText, setSearchText] = useState(() => searchParams.get(searchKey) || "")
  const [sorting, setSorting] = useState<SortingState>(() => sortingFromParam(searchParams.get(sortKey)))
  const activeSort = sorting[0]
  const sortParam = useMemo(() => sortingToParam(sorting), [sorting])

  const updateTableSearchParams = (next: {
    page?: number
    perPage?: number
    search?: string
    sorting?: SortingState
  }) => {
    const nextPage = next.page ?? page
    const nextPerPage = next.perPage ?? perPage
    const nextSearch = next.search ?? searchText
    const nextSorting = next.sorting ?? sorting
    const nextSortParam = sortingToParam(nextSorting)

    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (tab) params.set("tab", tab)
      if (nextPage === defaultPage) params.delete(pageKey)
      else params.set(pageKey, String(nextPage))
      if (nextPerPage === defaultPerPage) params.delete(perPageKey)
      else params.set(perPageKey, String(nextPerPage))
      if (nextSearch.trim()) params.set(searchKey, nextSearch)
      else params.delete(searchKey)
      if (nextSortParam) params.set(sortKey, nextSortParam)
      else params.delete(sortKey)
      return params
    }, { replace: true })
  }

  useEffect(() => {
    const urlPage = positiveIntParam(searchParams.get(pageKey), defaultPage)
    const urlPerPage = positiveIntParam(searchParams.get(perPageKey), defaultPerPage)
    const urlSearch = searchParams.get(searchKey) || ""
    const urlSorting = sortingFromParam(searchParams.get(sortKey))
    const urlSortParam = sortingToParam(urlSorting)

    if (urlPage !== page) setPage(urlPage)
    if (urlPerPage !== perPage) setPerPage(urlPerPage)
    if (urlSearch !== searchText) setSearchText(urlSearch)
    if (urlSortParam !== sortParam) setSorting(urlSorting)
  }, [
    defaultPage,
    defaultPerPage,
    page,
    pageKey,
    perPage,
    perPageKey,
    searchKey,
    searchParams,
    searchText,
    sortKey,
    sortParam,
  ])

  return {
    page,
    perPage,
    searchText,
    sorting,
    activeSort,
    sortParam,
    setPage,
    setPerPage,
    setSearchText,
    setSorting,
    updateTableSearchParams,
  }
}
