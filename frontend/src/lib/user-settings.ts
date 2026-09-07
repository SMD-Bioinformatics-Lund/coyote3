import { useMutation, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type { CurrentUserAccess } from "@/lib/access-control"

export type AnalysisLayout = "classic" | "modern"
export type SampleListLayout = "classic" | "modern"
export type UserUiSettings = Required<NonNullable<CurrentUserAccess["ui_settings"]>>
export const TABLE_PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const
export const DEFAULT_TABLE_PAGE_SIZE = 50

type AuthSession = {
  user?: CurrentUserAccess
  [key: string]: unknown
}

export function normalizeUserUiSettings(
  value: Partial<UserUiSettings> | null | undefined,
): UserUiSettings {
  return {
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
  return useMutation({
    mutationFn: (updates: Partial<UserUiSettings>) =>
      api.patch<{ status: string; ui_settings: UserUiSettings }>(
        "/users/me/ui-settings",
        updates,
      ).then((response) => response.data),
    onMutate: async (updates) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ["whoami"] }),
        queryClient.cancelQueries({ queryKey: ["auth-session"] }),
      ])
      const previous = queryClient.getQueryData<CurrentUserAccess>(["whoami"])
      const previousSession = queryClient.getQueryData<AuthSession>(["auth-session"])
      queryClient.setQueryData<CurrentUserAccess>(["whoami"], (current) => (
        current
          ? { ...current, ui_settings: { ...current.ui_settings, ...updates } }
          : current
      ))
      queryClient.setQueryData<AuthSession>(["auth-session"], (current) => (
        current?.user
          ? { ...current, user: { ...current.user, ui_settings: { ...current.user.ui_settings, ...updates } } }
          : current
      ))
      return { previous, previousSession }
    },
    onError: (_error, _updates, context) => {
      if (context?.previous) queryClient.setQueryData(["whoami"], context.previous)
      if (context?.previousSession) queryClient.setQueryData(["auth-session"], context.previousSession)
    },
    onSuccess: (response) => {
      queryClient.setQueryData<CurrentUserAccess>(["whoami"], (current) => (
        current
          ? { ...current, ui_settings: response.ui_settings }
          : current
      ))
      queryClient.setQueryData<AuthSession>(["auth-session"], (current) => (
        current?.user
          ? { ...current, user: { ...current.user, ui_settings: response.ui_settings } }
          : current
      ))
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["whoami"] }),
        queryClient.invalidateQueries({ queryKey: ["auth-session"] }),
      ])
    },
  })
}
