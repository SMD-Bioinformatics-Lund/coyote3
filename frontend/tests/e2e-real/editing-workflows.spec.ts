// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { expect, test } from "@playwright/test"
import { signIn, state } from "./support/session"

test("two browser editors cannot overwrite each other and the next editor loads the saved revision", async ({ page, browser }) => {
  await signIn(page)
  await page.goto("admin/users/browser.viewer/edit")
  await expect(page.getByRole("button", { name: "Save", exact: true }).first()).toBeVisible()
  const context = await browser.newContext({ baseURL: state.baseURL })
  try {
    const second = await context.newPage()
    await signIn(second, state.username)
    await second.goto("admin/users/browser.viewer/edit")
    await expect(second.getByText(/is editing this document/)).toBeVisible()
    await expect(second.getByRole("button", { name: "Save", exact: true })).toHaveCount(0)
    await page.getByLabel(/job title/i).fill("Synthetic reviewer after lease-protected edit")
    const saved = page.waitForResponse(r => r.url().endsWith("/users/browser.viewer") && r.request().method() === "PUT")
    await page.getByRole("button", { name: "Save", exact: true }).first().click()
    expect((await saved).status()).toBe(200)
    await expect(page).toHaveURL(/\/admin\/users$/)
    await second.getByRole("button", { name: "Reload document", exact: true }).click()
    await expect(second.getByRole("button", { name: "Save", exact: true }).first()).toBeVisible()
    await expect(second.getByLabel(/job title/i)).toHaveValue("Synthetic reviewer after lease-protected edit")
  } finally { await context.close() }
})

test("anonymous requests cannot read sample, report or administration data", async ({ page }) => {
  for (const route of [`samples/${state.dnaSample}/edit-context`, `samples/${state.dnaSample}/reports/dna/preview`, "reports", "users", "admin/audit"]) {
    const response = await page.request.get(`api/v1/${route}`)
    expect(response.status()).toBe(401)
    expect(await response.text()).not.toContain("DEMO_STARTER_DNA")
  }
  await page.goto(`samples/${state.dnaSample}`)
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible()
})
