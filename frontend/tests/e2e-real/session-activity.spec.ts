// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { expect, test } from "@playwright/test"
import type { SessionActivitySummary } from "../../src/lib/generated"
import { csrfHeaders, signIn, state } from "./support/session"

test("login activity counts one user across sessions and removes logged-out sessions", async ({ page, browser }) => {
  await signIn(page)
  const readCounts = async () => {
    const response = await page.request.get("api/v1/users/session-activity")
    expect(response.ok()).toBe(true)
    expect(response.headers()["cache-control"].split(",").map(value => value.trim())).toContain("no-store")
    return await response.json() as SessionActivitySummary
  }
  const before = await readCounts()
  expect(before.signed_in_users).toBeGreaterThan(0)
  const other = await browser.newContext({ baseURL: state.baseURL })
  try {
    await signIn(await other.newPage())
    const signedIn = await readCounts()
    expect(signedIn.signed_in_users).toBe(before.signed_in_users)
    expect(signedIn.active_sessions).toBe(before.active_sessions + 1)

    await page.goto("admin/users")
    const activity = page.getByRole("region", { name: "Login activity" })
    await expect(activity.getByText(String(signedIn.active_sessions), { exact: true })).toBeVisible()

    const logout = await other.request.delete("api/v1/auth/sessions/current", {
      headers: await csrfHeaders(other.request),
    })
    expect(logout.ok()).toBe(true)
    expect((await other.request.get("api/v1/users/session-activity")).status()).toBe(401)
    const signedOut = await readCounts()
    expect(signedOut.signed_in_users).toBe(before.signed_in_users)
    expect(signedOut.active_sessions).toBe(before.active_sessions)
    const refreshed = page.waitForResponse(response => response.url().endsWith("/users/session-activity"))
    await activity.getByRole("button", { name: "Refresh", exact: true }).click()
    expect((await (await refreshed).json()).active_sessions).toBe(before.active_sessions)
  } finally {
    await other.close()
  }
})

test("user administrators cannot access superuser login counts", async ({ page }) => {
  await signIn(page, state.username)
  const response = await page.request.get("api/v1/users/session-activity")
  expect(response.status()).toBe(403)
  await page.goto("admin/users")
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible()
  await expect(page.getByRole("region", { name: "Login activity" })).toHaveCount(0)
})
