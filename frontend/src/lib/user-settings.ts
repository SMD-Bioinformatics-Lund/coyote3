import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { CurrentUserAccess } from "@/lib/access-control"

export type AnalysisLayout = "classic" | "modern"
export type SampleListLayout = "classic" | "modern"
export type UserUiSettings = Required<NonNullable<CurrentUserAccess["ui_settings"]>>
export const TABLE_PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const
export const DEFAULT_TABLE_PAGE_SIZE = 200

type AuthSession = {
  user?: CurrentUserAccess
  [key: string]: unknown
}

type SettingsBatch = {
  username: string
  confirmed: UserUiSettings
  pending: Map<symbol, Partial<UserUiSettings>>
}
const settingsBatches = new WeakMap<QueryClient, Map<string, SettingsBatch>>()

function settingsUser(client: QueryClient) {
  return client.getQueryData<CurrentUserAccess>(["whoami"])
    ?? client.getQueryData<AuthSession>(["auth-session"])?.user
}

/** Reapply pending edits over confirmed settings without replacing account identity. */
function displaySettings(client: QueryClient, batch: SettingsBatch) {
  const settings = Object.assign({}, batch.confirmed, ...batch.pending.values())
  client.setQueryData<CurrentUserAccess>(["whoami"], current => current?.username === batch.username
    ? { ...current, ui_settings: settings } : current)
  client.setQueryData<AuthSession>(["auth-session"], current => current?.user?.username === batch.username
    ? { ...current, user: { ...current.user, ui_settings: settings } } : current)
}

export function normalizeUserUiSettings(
  value: Partial<UserUiSettings> | null | undefined,
): UserUiSettings {
  return {
    theme: value?.theme === "light" || value?.theme === "dark" ? value.theme : "auto",
    analysis_layout: value?.analysis_layout === "modern" ? "modern" : "classic",
    sample_list_layout: value?.sample_list_layout === "modern" ? "modern" : "classic",
    analysis_modern_view_tried: Boolean(value?.analysis_modern_view_tried),
    sample_list_modern_view_tried: Boolean(value?.sample_list_modern_view_tried),
    table_page_size: TABLE_PAGE_SIZE_OPTIONS.includes(value?.table_page_size as typeof TABLE_PAGE_SIZE_OPTIONS[number])
      ? Number(value?.table_page_size)
      : DEFAULT_TABLE_PAGE_SIZE,
  }
}

export function tablePageSizeForUser(user: CurrentUserAccess | null | undefined): number {
  const value = user?.ui_settings?.table_page_size
  return TABLE_PAGE_SIZE_OPTIONS.includes(value as typeof TABLE_PAGE_SIZE_OPTIONS[number])
    ? Number(value)
    : DEFAULT_TABLE_PAGE_SIZE
}

export function analysisLayoutForUser(user: CurrentUserAccess | null | undefined): AnalysisLayout {
  return user?.ui_settings?.analysis_layout === "modern" ? "modern" : "classic"
}

export function sampleListLayoutForUser(user: CurrentUserAccess | null | undefined): SampleListLayout {
  return user?.ui_settings?.sample_list_layout === "modern" ? "modern" : "classic"
}

export function analysisModernViewTriedForUser(user: CurrentUserAccess | null | undefined): boolean {
  return Boolean(
    user?.ui_settings?.analysis_modern_view_tried ||
    user?.ui_settings?.analysis_layout === "modern",
  )
}

export function sampleListModernViewTriedForUser(user: CurrentUserAccess | null | undefined): boolean {
  return Boolean(
    user?.ui_settings?.sample_list_modern_view_tried ||
    user?.ui_settings?.sample_list_layout === "modern",
  )
}

export function useUpdateUiSettings() {
  const queryClient = useQueryClient()
  const username = settingsUser(queryClient)?.username
  return useMutation({
    scope: { id: "user-ui-settings" },
    mutationFn: (updates: Partial<UserUiSettings>) => {
      if (!username || settingsUser(queryClient)?.username !== username) {
        throw new Error("Your account changed. Save preferences again from the current account.")
      }
      return api.patch<{ status: string; ui_settings: UserUiSettings }>(
        "/users/me/ui-settings",
        updates,
      ).then((response) => response.data)
    },
    onMutate: async (updates) => {
      const user = settingsUser(queryClient)
      if (!username || user?.username !== username) throw new Error("Your account changed.")
      const batches = settingsBatches.get(queryClient) ?? new Map<string, SettingsBatch>()
      settingsBatches.set(queryClient, batches)
      const batch = batches.get(username) ?? {
        username, confirmed: normalizeUserUiSettings(user.ui_settings), pending: new Map(),
      }
      batches.set(username, batch)
      const token = Symbol()
      batch.pending.set(token, updates)
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ["whoami"] }),
        queryClient.cancelQueries({ queryKey: ["auth-session"] }),
      ])
      displaySettings(queryClient, batch)
      return { batch, token }
    },
    onSettled: async (response, _error, _updates, context) => {
      if (!context) return
      const { batch, token } = context
      if (response) batch.confirmed = response.ui_settings
      batch.pending.delete(token)
      displaySettings(queryClient, batch)
      if (batch.pending.size) return
      settingsBatches.get(queryClient)?.delete(batch.username)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["whoami"] }),
        queryClient.invalidateQueries({ queryKey: ["auth-session"] }),
      ])
    },
  })
}
