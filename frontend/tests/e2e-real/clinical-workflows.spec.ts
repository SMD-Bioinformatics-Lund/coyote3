// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { expect, test } from "@playwright/test"
import { csrfHeaders, openReport, openSample, reportLibrary, signIn, state } from "./support/session"

// Each scenario runs in a fresh browser context against this run's synthetic records.
test("a scoped reader can open DNA but cannot read RNA or administer users", async ({ page }) => {
  await signIn(page, "browser.viewer")
  await openSample(page)
  await expect(page.getByRole("tab", { name: /^(Somatic )?SNVs$/ }).first()).toBeVisible()
  const allowed = await page.request.get(`api/v1/samples/${state.dnaSample}/edit-context`)
  expect(allowed.status()).toBe(200)
  const catalog = await (await page.request.get("api/v1/samples?profile_scope=all")).json()
  expect([...catalog.live_samples, ...catalog.done_samples].map(sample => sample.name)).toEqual([state.dnaSample])
  const forbidden = await page.request.get(`api/v1/samples/${state.rnaSample}/edit-context`)
  expect(forbidden.status()).toBe(403)
  expect(await forbidden.text()).not.toContain("DEMO_STARTER_RNA")
  expect((await page.request.get("api/v1/users")).status()).toBe(403)
  const save = await page.request.post(`api/v1/samples/${state.dnaSample}/reports/dna`, {
    headers: await csrfHeaders(page.request), data: { preview_fingerprint: "invalid" },
  })
  expect(save.status()).toBe(403)
})

test("assay permission in production does not grant access to a testing sample", async ({ page }) => {
  await signIn(page, "browser.no-scope")
  const list = await page.request.get("api/v1/samples?profile_scope=all")
  expect(list.status()).toBe(200)
  const payload = await list.json()
  expect([...payload.live_samples, ...payload.done_samples]).toEqual([])
  expect((await page.request.get(`api/v1/samples/${state.dnaSample}/edit-context`)).status()).toBe(403)
  await page.goto(`samples/${state.dnaSample}`)
  await expect(page.getByRole("tab", { name: "Reports", exact: true })).toHaveCount(0)
  await expect(page.getByText(/Sample is outside your access scope/).first()).toBeVisible()
})

test("a browser session without CSRF proof cannot append a clinical comment", async ({ page }) => {
  await signIn(page, "browser.reviewer")
  const path = `api/v1/samples/${state.dnaSample}/edit-context`
  const before = await (await page.request.get(path)).json()
  const blocked = await page.request.post(`api/v1/samples/${state.dnaSample}/comments`, {
    headers: { Origin: new URL(state.baseURL).origin }, data: { form_data: { sample_comment: "REJECTED_CSRF_COMMENT" } },
  })
  expect(blocked.status()).toBe(403)
  const after = await (await page.request.get(path)).json()
  expect(after.comments).toEqual(before.comments)
})

test("a saved comment survives reload and its markup cannot execute script", async ({ page }) => {
  await signIn(page, "browser.reviewer")
  await openSample(page)
  await page.getByRole("tab", { name: /^(Somatic )?SNVs$/ }).first().click()
  const editor = page.getByPlaceholder("Write a markdown comment...")
  await editor.fill('**Synthetic review:**\n\nPersistent browser review. <img src=x onerror="window.coyoteUnsafe=true">')
  const saved = page.waitForResponse(r => r.url().endsWith("/comments") && r.request().method() === "POST")
  await page.getByRole("button", { name: "Save comment", exact: true }).click()
  expect((await saved).status()).toBe(201)
  await page.reload()
  await expect(page.getByText("Persistent browser review.", { exact: false }).first()).toBeVisible()
  expect(await page.evaluate(() => (window as Window & { coyoteUnsafe?: boolean }).coyoteUnsafe)).toBeUndefined()
  const comments = page.locator(".sample-comments")
  await expect(comments.locator("img[onerror], script")).toHaveCount(0)
  await expect(comments.locator("strong").filter({ hasText: "Synthetic review:" }).first()).toBeVisible()
})

test("cancelling report confirmation leaves the report library unchanged", async ({ page }) => {
  await signIn(page, "browser.reviewer")
  const before = await reportLibrary(page)
  await openReport(page)
  await page.getByRole("button", { name: "Save report", exact: true }).click()
  const dialog = page.getByRole("alertdialog")
  await expect(dialog).toContainText("Confirm report save")
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(await reportLibrary(page)).toEqual(before)
})

test("stale preview is rejected visibly; refreshing permits a reviewed report save", async ({ page, browser }) => {
  await signIn(page, "browser.reviewer")
  const before = await reportLibrary(page)
  await openReport(page)
  // The confirmation holds the displayed preview while another real browser edits the source.
  await page.getByRole("button", { name: "Save report", exact: true }).click()
  const other = await browser.newContext({ baseURL: state.baseURL })
  try {
    const editor = await other.newPage()
    await signIn(editor, "browser.reviewer")
    const update = await editor.request.post(`api/v1/samples/${state.dnaSample}/comments`, {
      headers: await csrfHeaders(editor.request), data: { form_data: { sample_comment: "Synthetic concurrent report revision." } },
    })
    expect(update.status()).toBe(201)
    const rejected = page.waitForResponse(r => r.url().endsWith("/reports/dna") && r.request().method() === "POST")
    await page.getByRole("button", { name: "Confirm save", exact: true }).click()
    expect((await rejected).status()).toBe(409)
    await expect(page.getByText(/Report inputs changed\. Refresh and review the preview before saving/).first()).toBeVisible()
    expect(await reportLibrary(page)).toEqual(before)
    await page.getByRole("alertdialog").getByRole("button", { name: "Cancel", exact: true }).click()
    const refreshed = page.waitForResponse(r => new URL(r.url()).pathname.endsWith("/reports/dna/preview"))
    await page.getByRole("button", { name: "Refresh", exact: true }).click()
    expect((await refreshed).status()).toBe(200)
    await page.getByRole("button", { name: "Save report", exact: true }).click()
    const saved = page.waitForResponse(r => r.url().endsWith("/reports/dna") && r.request().method() === "POST")
    await page.getByRole("button", { name: "Confirm save", exact: true }).click()
    expect((await saved).status()).toBe(201)
    await expect(page.getByRole("alertdialog")).toBeHidden()
    expect((await reportLibrary(page)).length).toBe(before.length + 1)
  } finally { await other.close() }
})

test("saved HTML, PDF and finding snapshots remain unchanged after source comments change", async ({ page }) => {
  await signIn(page, "browser.reviewer")
  await openReport(page)
  await page.getByRole("button", { name: "Save report", exact: true }).click()
  const saving = page.waitForResponse(r => r.url().endsWith("/reports/dna") && r.request().method() === "POST")
  await page.getByRole("button", { name: "Confirm save", exact: true }).click()
  const response = await saving
  expect(response.status()).toBe(201)
  const saved = await response.json()
  expect(saved.report.snapshot_count).toBe(3)
  const id = encodeURIComponent(saved.report.id)
  const path = `api/v1/samples/${state.dnaSample}/reports/${id}`
  const html = await page.request.get(`${path}/download`)
  const pdf = await page.request.get(`${path}/pdf`)
  expect(html.status()).toBe(200)
  expect(pdf.status()).toBe(200)
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-")
  const metadata = (await reportLibrary(page)).find(report => report.report_id === saved.report.id)
  expect(metadata?.finding_count).toBe(3)
  const update = await page.request.post(`api/v1/samples/${state.dnaSample}/comments`, {
    headers: await csrfHeaders(page.request), data: { form_data: { sample_comment: "AFTER_IMMUTABLE_REPORT_SAVED" } },
  })
  expect(update.status()).toBe(201)
  await page.reload()
  expect(await (await page.request.get(`${path}/download`)).body()).toEqual(await html.body())
  expect(await (await page.request.get(`${path}/pdf`)).body()).toEqual(await pdf.body())
  expect((await reportLibrary(page)).find(report => report.report_id === saved.report.id)).toEqual(metadata)
  expect(await html.text()).not.toContain("AFTER_IMMUTABLE_REPORT_SAVED")
})

test("logout invalidates the server session rather than only clearing browser UI", async ({ page, playwright }) => {
  await signIn(page, "browser.reviewer")
  const copied = await page.context().storageState()
  const result = await page.request.delete("api/v1/auth/sessions/current", { headers: await csrfHeaders(page.request) })
  expect(result.ok()).toBe(true)
  const replay = await playwright.request.newContext({ baseURL: state.baseURL, storageState: copied })
  try {
    expect((await replay.get("api/v1/auth/whoami")).status()).toBe(401)
  } finally { await replay.dispose() }
  await page.goto(`samples/${state.dnaSample}`)
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible()
})
