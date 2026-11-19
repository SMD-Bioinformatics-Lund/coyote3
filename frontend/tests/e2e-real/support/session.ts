// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { expect, type APIRequestContext, type Page } from "@playwright/test"
import { stackState } from "./disposable-stack"

export const state = stackState()

export async function signIn(page: Page, username = state.superuser) {
  const providers = page.waitForResponse(response => response.url().endsWith("/auth/providers") && response.ok())
  await page.goto("login")
  await providers
  const local = page.getByRole("button", { name: "Local Account" })
  const input = page.getByLabel("Username")
  await expect(local.or(input).first()).toBeVisible()
  if (await local.isVisible()) await local.click()
  await input.fill(username)
  await page.getByLabel("Password", { exact: true }).fill(state.reviewPassword)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
}

export async function csrfHeaders(request: APIRequestContext) {
  const response = await request.get("api/v1/auth/whoami")
  expect(response.ok()).toBe(true)
  return { "X-CSRF-Token": (await response.json()).csrf_token, Origin: new URL(state.baseURL).origin }
}

export async function openSample(page: Page, sample = state.dnaSample) {
  await page.goto(`samples/${encodeURIComponent(sample)}`)
  await page.getByRole("tab", { name: "Modern", exact: true }).click()
}

export async function openReport(page: Page, sample = state.dnaSample) {
  await openSample(page, sample)
  const preview = page.waitForResponse(r => r.url().includes("/reports/") && new URL(r.url()).pathname.endsWith("/preview"))
  await page.getByRole("tab", { name: "Reports", exact: true }).click()
  const response = await preview
  expect(response.ok()).toBe(true)
  await expect(page.getByRole("button", { name: "Save report", exact: true })).toBeEnabled()
  return response.json()
}

export async function reportLibrary(page: Page) {
  const response = await page.request.get(`api/v1/reports?search=${state.dnaSample}`)
  expect(response.ok()).toBe(true)
  return (await response.json()).reports as Array<Record<string, unknown>>
}
