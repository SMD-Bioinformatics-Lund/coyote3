import type { PropsWithChildren } from "react"
import { act, renderHook } from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useClinicalTableState } from "./useClinicalTableState"
import { useUrlTableState } from "./useUrlTableState"

function router(entry: string) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <MemoryRouter initialEntries={[entry]}>{children}</MemoryRouter>
  }
}

describe("URL-backed table state", () => {
  it("parses paging, search, and multi-column sorting from the URL", () => {
    const { result } = renderHook(() => ({
      table: useUrlTableState({ prefix: "variants", tab: "snvs" }),
      location: useLocation(),
    }), { wrapper: router("/samples/CASE?variants_page=3&variants_per_page=100&variants_q=TP53&variants_sort=vaf:desc,gene:asc") })

    expect(result.current.table.page).toBe(3)
    expect(result.current.table.perPage).toBe(100)
    expect(result.current.table.searchText).toBe("TP53")
    expect(result.current.table.sorting).toEqual([{ id: "vaf", desc: true }, { id: "gene", desc: false }])
    expect(result.current.table.activeSort).toEqual({ id: "vaf", desc: true })
  })

  it("writes changes and removes values equal to defaults", () => {
    const { result } = renderHook(() => ({
      table: useUrlTableState({ prefix: "cnv", tab: "cnvs", defaultPerPage: 50 }),
      location: useLocation(),
    }), { wrapper: router("/samples/CASE?preserved=yes") })

    act(() => result.current.table.updateTableSearchParams({
      page: 2,
      perPage: 100,
      search: "  gain ",
      sorting: [{ id: "copy_number", desc: true }],
    }))
    expect(result.current.location.search).toContain("preserved=yes")
    expect(result.current.location.search).toContain("tab=cnvs")
    expect(result.current.location.search).toContain("cnv_page=2")
    expect(result.current.location.search).toContain("cnv_sort=copy_number%3Adesc")

    act(() => result.current.table.updateTableSearchParams({ page: 1, perPage: 50, search: "", sorting: [] }))
    expect(result.current.location.search).toBe("?preserved=yes&tab=cnvs")
  })

  it("falls back for malformed positive integer parameters", () => {
    const { result } = renderHook(() => useUrlTableState({ prefix: "table", defaultPage: 2, defaultPerPage: 25 }), {
      wrapper: router("/?table_page=-5&table_per_page=nope&table_sort=:desc,valid:weird"),
    })
    expect(result.current.page).toBe(2)
    expect(result.current.perPage).toBe(25)
    expect(result.current.sorting).toEqual([{ id: "valid", desc: false }])
  })
})

describe("clinical table state", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("debounces trimmed searches and exposes stable server query state", () => {
    const { result } = renderHook(() => useClinicalTableState({ prefix: "snv", searchDebounceMs: 200 }), {
      wrapper: router("/samples/CASE"),
    })
    act(() => result.current.tableProps.onSearchChange("  TP53  "))
    expect(result.current.debouncedSearchText).toBe("")
    act(() => vi.advanceTimersByTime(200))
    expect(result.current.debouncedSearchText).toBe("TP53")
    expect(result.current.queryKeyState).toEqual([1, 50, "TP53", ""])
  })

  it("resets the page when page size or sorting changes", () => {
    const { result } = renderHook(() => useClinicalTableState({ prefix: "snv" }), {
      wrapper: router("/?snv_page=4"),
    })
    expect(result.current.page).toBe(4)
    act(() => result.current.tableProps.onPerPageChange(100))
    expect(result.current.page).toBe(1)
    expect(result.current.perPage).toBe(100)
    act(() => result.current.tableProps.onSortingChange([{ id: "vaf", desc: true }, { id: "gene", desc: false }]))
    expect(result.current.sorting).toHaveLength(2)
    expect(result.current.sortParam).toBe("vaf:desc,gene:asc")
  })

  it("preserves the canonical somatic SNV tab when sorting", () => {
    const { result } = renderHook(() => ({
      table: useClinicalTableState({ prefix: "snv-somatic", tab: "snvs" }),
      location: useLocation(),
    }), { wrapper: router("/samples/CASE?tab=snvs") })

    act(() => result.current.table.tableProps.onSortingChange([{ id: "tier", desc: false }]))

    expect(result.current.location.search).toContain("tab=snvs")
    expect(result.current.location.search).toContain("snv-somatic_sort=tier%3Aasc")
    expect(result.current.location.search).not.toContain("tab=somatic-snvs")
  })
})
