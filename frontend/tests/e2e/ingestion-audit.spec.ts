import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  for (const width of [390, 1440]) {
    test(`ingestion audit ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 960 })
      await installApiFixtures(page, (path, url) => {
        if (path === "/api/v1/auth/whoami") return { json: { username: "synthetic_admin", roles: ["superuser"], permissions: ["audit_log:view"], ui_settings: { theme } } }
        if (path === "/api/v1/admin/audit") {
          expect(url.searchParams.get("ingestion_only")).toBe("true")
          return { json: { total: 2, events: [
            { _id: "terminal", occurred_at: "2026-10-29T12:01:00Z", event_type: "ingest.attempt.unconfirmed", message: "Ingestion outcome needs reconciliation", outcome: "failure", actor: { username: "synthetic_admin" }, metadata: { attempt_id: "synthetic-attempt", source: "upload", manifest: "synthetic.yaml", error: "Connection interrupted; inspect the committed result before retrying." } },
            { _id: "started", occurred_at: "2026-10-29T12:00:00Z", event_type: "ingest.attempt.started", message: "Ingestion started", outcome: "success", metadata: { attempt_id: "synthetic-attempt", source: "upload", manifest: "synthetic.yaml" } },
          ] } }
        }
        return undefined
      })
      await page.goto("/admin/ingestion-audit")
      await expect(page.getByRole("heading", { name: "Ingestion audit", exact: true })).toBeVisible()
      await expect(page.getByRole("table")).toBeVisible()
      await page.getByLabel("Outcome", { exact: true }).selectOption("Needs reconciliation")
      const inspect = page.getByRole("button", { name: "Inspect Ingestion outcome needs reconciliation" })
      await inspect.focus()
      await page.keyboard.press("Enter")
      const detail = page.getByRole("region", { name: "Ingestion attempt details" })
      await expect(detail).toBeFocused()
      await expect(detail).toContainText("Ingestion started")
      await expect(detail).toContainText("Connection interrupted")
      await page.screenshot({ path: testInfo.outputPath(`ingestion-audit-${theme}-${width}.png`), fullPage: true })
    })
  }
}
