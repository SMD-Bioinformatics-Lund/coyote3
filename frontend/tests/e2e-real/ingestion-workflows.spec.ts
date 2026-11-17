// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import path from "node:path"
import { expect, test, type Page } from "@playwright/test"
import { openSample, signIn, state } from "./support/session"
import { setWorkerRunning } from "./support/disposable-stack"

async function upload(page: Page, name: "valid" | "invalid" | "wgs") {
  await page.goto("admin/ingest")
  await expect(page.getByRole("heading", { name: "Ingest Workspace", exact: true })).toBeVisible()
  const bundles = path.join(path.dirname(process.env.COYOTE4_E2E_STATE!), "bundles")
  await page.getByLabel("YAML manifest", { exact: true }).setInputFiles(path.join(bundles, `${name}.yaml`))
  await page.getByLabel("Referenced data archive", { exact: true }).setInputFiles(path.join(bundles, "data.zip"))
  const submitted = page.waitForResponse(response => response.url().endsWith("/sample-bundle/upload/async"))
  await page.getByRole("button", { name: "Queue ingest", exact: true }).click()
  const response = await submitted
  expect(response.status()).toBe(202)
  return (await response.json()).task_id as string
}

test("queued upload survives worker downtime and appears once after recovery", async ({ page }) => {
  test.setTimeout(120_000)
  await signIn(page)
  setWorkerRunning(state, false)
  try {
    const id = await upload(page, "valid")
    await expect(page.getByText(id, { exact: true })).toBeVisible()
    const pending = await page.request.get(`api/v1/internal/tasks/${id}`)
    expect(pending.status()).toBe(200)
    expect((await pending.json()).ready).toBe(false)
    const samples = await page.request.get("api/v1/samples?profile_scope=all&search_str=DEMO_BROWSER_VALID")
    const pendingSamples = await samples.json()
    expect([...pendingSamples.live_samples, ...pendingSamples.done_samples]).toEqual([])
    setWorkerRunning(state, true)
    await expect(page.getByText("SUCCESS", { exact: true })).toBeVisible({ timeout: 60_000 })
    const finished = await page.request.get(`api/v1/internal/tasks/${id}`)
    expect((await finished.json()).successful).toBe(true)
    const after = await page.request.get("api/v1/samples?profile_scope=all&search_str=DEMO_BROWSER_VALID")
    const catalog = await after.json()
    const results = [...catalog.live_samples, ...catalog.done_samples]
    expect(results.filter((sample: { name: string }) => sample.name === "DEMO_BROWSER_VALID")).toHaveLength(1)
    await page.goto("samples/DEMO_BROWSER_VALID")
    await expect(page.getByRole("tab", { name: "Modern", exact: true })).toBeVisible()
  } finally { setWorkerRunning(state, true) }
})

test("invalid paired upload is visibly failed and publishes no partial sample", async ({ page }) => {
  test.setTimeout(90_000)
  await signIn(page)
  const id = await upload(page, "invalid")
  await expect(page.getByText("FAILURE", { exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText("Ingest failed", { exact: true }).first()).toBeVisible()
  const status = await (await page.request.get(`api/v1/internal/tasks/${id}`)).json()
  expect(status.ready).toBe(true)
  expect(status.successful).toBe(false)
  const samples = await (await page.request.get("api/v1/samples?profile_scope=all&search_str=DEMO_BROWSER_INVALID")).json()
  expect([...samples.live_samples, ...samples.done_samples]).toEqual([])
  await page.goto("admin/ingestion-audit")
  await expect(page.getByRole("heading", { name: "Ingestion audit", exact: true })).toBeVisible()
  await expect(page.getByRole("table")).toContainText(/failed|failure/i)
})


test("a WGS upload exposes its CNVs, DNA translocations and SNVs in the analysis tables", async ({ page }) => {
  test.setTimeout(90_000)
  await signIn(page)
  await upload(page, "wgs")
  await expect(page.getByText("SUCCESS", { exact: true })).toBeVisible({ timeout: 60_000 })
  await openSample(page, "DEMO_BROWSER_WGS")
  await page.getByRole("tab", { name: "CNVs", exact: true }).click()
  await expect(page.getByRole("row").filter({ hasText: "TP53" }).first()).toBeVisible()
  await page.getByRole("tab", { name: "Translocations", exact: true }).click()
  const translocation = page.getByRole("row").filter({ hasText: "BCR" }).filter({ hasText: "ABL1" })
  await expect(translocation.first()).toBeVisible()
  await page.getByRole("tab", { name: /^(Somatic )?SNVs$/ }).first().click()
  await expect(page.getByRole("row").filter({ hasText: "TP53" }).first()).toBeVisible()
})
