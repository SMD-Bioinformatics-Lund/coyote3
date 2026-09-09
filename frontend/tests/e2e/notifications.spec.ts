import { expect, test } from "@playwright/test"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { installApiFixtures } from "./support/api-fixtures"

for (const width of [1440, 390]) {
  test(`broadcast tray and Markdown at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await installApiFixtures(page, (path) => path === "/api/v1/notifications" ? { json: {
      notifications: [{ id: "notice", title: "Scheduled maintenance and service availability",
        severity: "important", tone: "info", is_broadcast: true, can_clear: false,
        message: "## Maintenance\n\n**Save your work** before the scheduled restart.\n\n- Review active tasks\n- Sign in after maintenance\n\n<script>alert(1)</script>",
        created_at: "2026-09-01T10:00:00Z", created_by: "operator", read: false }], unread_count: 1,
    } } : undefined)
    await page.goto("/notifications")
    await expect(page.getByText("important", { exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "Clear", exact: true })).toBeDisabled()
    await expect(page.getByRole("button", { name: "Remove notification" })).toHaveCount(0)
    await expect(page.getByText("Save your work", { exact: true })).not.toBeVisible()
    await page.screenshot({ path: testInfo.outputPath("tray.png"), fullPage: true })
    await page.getByText("Scheduled maintenance and service availability").click()
    await expect(page.getByText("Save your work", { exact: true })).toBeVisible()
    expect(await page.locator(".markdown-body script").count()).toBe(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath("expanded.png"), fullPage: true })
  })
}

test("broadcast editor previews Markdown and sends expiry and severity", async ({ page }, testInfo) => {
  let payload: Record<string, unknown> | undefined
  await installApiFixtures(page, (path, _url, route) => {
    if (path === "/api/v1/admin/notifications/recipients") return { json: { users: [], roles: [] } }
    if (path === "/api/v1/admin/notifications/sent") return { json: { notifications: [] } }
    if (path === "/api/v1/admin/notifications/broadcast") {
      payload = route.request().postDataJSON()
      return { json: { recipient_count: 1, email_state: "pending" } }
    }
  })
  await page.goto("/admin/notifications")
  await page.getByLabel("Title", { exact: true }).fill("Scheduled maintenance")
  await page.getByLabel("Message", { exact: true }).fill("**Important** maintenance notice.")
  await page.getByLabel("Severity").selectOption("critical")
  await page.getByLabel("Expires at", { exact: false }).fill("2099-01-01T12:00")
  await page.getByRole("button", { name: "Preview", exact: true }).click()
  await expect(page.locator(".markdown-body strong")).toHaveText("Important")
  await page.screenshot({ path: testInfo.outputPath("composer.png"), fullPage: true })
  await page.getByRole("button", { name: "Send", exact: true }).click()
  await page.getByRole("button", { name: "Send notification", exact: true }).click()
  await expect.poll(() => payload?.severity).toBe("critical")
  expect(payload?.message).toBe("**Important** maintenance notice.")
  expect(String(payload?.expires_at)).toMatch(/Z$/)
})

test("branded email renders its bundled logo without external resources", async ({ page }, testInfo) => {
  const root = resolve(process.cwd(), "..")
  const html = execFileSync(resolve(root, ".venv/bin/python"), ["-c",
    "import base64; from api.infra.notifications.templates import render_email; from api.config.paths import EMAIL_LOGO_PATH; print(render_email(subject='Coyote3 service notice',text_body='A new message is available in your inbox.',severity='important',environment='test',action_url='https://example.test/notifications').replace('cid:coyote3-logo','data:image/png;base64,'+base64.b64encode(EMAIL_LOGO_PATH.read_bytes()).decode()))",
  ], { cwd: root, encoding: "utf8" })
  await page.setContent(html)
  await expect(page.getByRole("heading", { name: "Coyote3 service notice" })).toBeVisible()
  expect(await page.locator("img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath("email-desktop.png"), fullPage: true })
  await page.setViewportSize({ width: 390, height: 850 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath("email-mobile.png"), fullPage: true })
})
