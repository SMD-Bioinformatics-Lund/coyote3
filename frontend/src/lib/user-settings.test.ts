import { describe, expect, it, vi } from "vitest"
import { createElement, type PropsWithChildren } from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { api, type ApiResponse } from "@/lib/api"
import type { CurrentUserAccess } from "@/lib/access-control"

import {
  analysisLayoutForUser,
  analysisModernViewTriedForUser,
  normalizeUserUiSettings,
  sampleListLayoutForUser,
  sampleListModernViewTriedForUser,
  tablePageSizeForUser,
  useUpdateUiSettings,
} from "./user-settings"

describe("analysisLayoutForUser", () => {
  it("uses classic for new and existing users without an explicit preference", () => {
    expect(analysisLayoutForUser(undefined)).toBe("classic")
    expect(analysisLayoutForUser({} as never)).toBe("classic")
  })

  it("returns the persisted modern layout", () => {
    expect(analysisLayoutForUser({ ui_settings: { analysis_layout: "modern" } } as never)).toBe("modern")
  })

  it("uses classic for sample lists until modern is selected", () => {
    expect(sampleListLayoutForUser(undefined)).toBe("classic")
    expect(sampleListLayoutForUser({ ui_settings: { sample_list_layout: "modern" } } as never)).toBe("modern")
  })

  it("tracks modern-view discovery independently for analysis and sample lists", () => {
    expect(analysisModernViewTriedForUser(undefined)).toBe(false)
    expect(sampleListModernViewTriedForUser(undefined)).toBe(false)
    expect(analysisModernViewTriedForUser({
      ui_settings: { analysis_modern_view_tried: true },
    } as never)).toBe(true)
    expect(analysisModernViewTriedForUser({
      ui_settings: { analysis_layout: "modern" },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { sample_list_modern_view_tried: true },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { sample_list_layout: "modern" },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { analysis_modern_view_tried: true },
    } as never)).toBe(false)
  })

  it("normalizes and resolves the persisted table page size", () => {
    expect(normalizeUserUiSettings(undefined).table_page_size).toBe(200)
    expect(tablePageSizeForUser(undefined)).toBe(200)
    expect(tablePageSizeForUser({ ui_settings: { table_page_size: 100 } } as never)).toBe(100)
    expect(tablePageSizeForUser({ ui_settings: { table_page_size: 500 } } as never)).toBe(200)
  })
})

it.each([true, false])("does not overwrite a new account after a settings response (success: %s)", async success => {
  vi.restoreAllMocks()
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const first: CurrentUserAccess = { username: "first", roles: [], role: "user", permissions: [], access_level: 1 }
  const second = { ...first, username: "second", ui_settings: { theme: "light" as const } }
  client.setQueryData(["whoami"], first)
  client.setQueryData(["auth-session"], { user: first })
  let resolve!: (value: ApiResponse<unknown>) => void
  let reject!: (reason: Error) => void
  const patch = vi.spyOn(api, "patch").mockImplementation(() => new Promise((yes, no) => { resolve = yes; reject = no }))
  const { result } = renderHook(useUpdateUiSettings, {
    wrapper: ({ children }: PropsWithChildren) => createElement(QueryClientProvider, { client }, children),
  })
  act(() => result.current.mutate({ theme: "dark" }))
  await waitFor(() => expect(patch).toHaveBeenCalled())
  client.setQueryData(["whoami"], second)
  client.setQueryData(["auth-session"], { user: second })
  await act(async () => {
    if (success) resolve({ status: 200, data: { ui_settings: normalizeUserUiSettings({ theme: "dark" }) } })
    else reject(new Error("Request failed"))
  })
  await waitFor(() => expect(result.current.isPending).toBe(false))
  expect(client.getQueryData(["whoami"])).toEqual(second)
  expect(client.getQueryData(["auth-session"])).toEqual({ user: second })
  patch.mockRestore()
})

it.each([[true, true], [true, false], [false, true], [false, false]])("preserves overlapping settings edits (first succeeds: %s, second: %s)", async (firstSucceeds, secondSucceeds) => {
  vi.restoreAllMocks()
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const baseline = normalizeUserUiSettings({ theme: "light" })
  const user: CurrentUserAccess = { username: "first", roles: [], role: "user", permissions: [], access_level: 1, ui_settings: baseline }
  client.setQueryData(["whoami"], user)
  client.setQueryData(["auth-session"], { user })
  const requests: Array<{ resolve: (value: ApiResponse<unknown>) => void; reject: (error: Error) => void }> = []
  const patch = vi.spyOn(api, "patch").mockImplementation(() => new Promise((resolve, reject) => requests.push({ resolve, reject })))
  const { result } = renderHook(() => [useUpdateUiSettings(), useUpdateUiSettings()], {
    wrapper: ({ children }: PropsWithChildren) => createElement(QueryClientProvider, { client }, children),
  })
  act(() => result.current[0].mutate({ theme: "dark" }))
  await waitFor(() => expect(requests).toHaveLength(1))
  act(() => result.current[1].mutate({ theme: "auto", table_page_size: 50 }))
  await waitFor(() => expect(client.getQueryData<CurrentUserAccess>(["whoami"])?.ui_settings?.theme).toBe("auto"))
  expect(requests).toHaveLength(1)
  await act(async () => {
    if (firstSucceeds) requests[0].resolve({ status: 200, data: { ui_settings: { ...baseline, theme: "dark" } } })
    else requests[0].reject(new Error("First save failed"))
  })
  await waitFor(() => expect(requests).toHaveLength(2))
  expect(client.getQueryData<CurrentUserAccess>(["whoami"])?.ui_settings).toMatchObject({ theme: "auto", table_page_size: 50 })
  await act(async () => {
    if (secondSucceeds) requests[1].resolve({ status: 200, data: { ui_settings: { ...baseline, theme: "auto", table_page_size: 50 } } })
    else requests[1].reject(new Error("Second save failed"))
  })
  await waitFor(() => expect(result.current[1].isPending).toBe(false))
  const expected = secondSucceeds ? { ...baseline, theme: "auto", table_page_size: 50 }
    : { ...baseline, theme: firstSucceeds ? "dark" : "light" }
  expect(client.getQueryData<CurrentUserAccess>(["whoami"])?.ui_settings).toEqual(expected)
  expect(client.getQueryData<{ user: CurrentUserAccess }>(["auth-session"])?.user.ui_settings).toEqual(expected)
  patch.mockRestore()
})
