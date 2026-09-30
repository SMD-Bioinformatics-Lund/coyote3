import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("saved reports block active HTML and retain a stable readable height", async ({ page }) => {
  await installApiFixtures(page, (path) => {
    if (path.endsWith("/reports/report_demo/context")) {
      return { json: { sample_id: "sample_demo", report_id: "report_demo", findings: [], finding_count: 0, analysis_counts: {} } }
    }
  })
  await page.route("**/reports/report_demo/html", (route) => route.fulfill({
    contentType: "text/html",
    body: `<html><body><h1>Synthetic report</h1><div style="height:900px">Report content</div>
      <script>parent.document.body.dataset.reportExecuted = 'yes'</script>
      <img src="/missing-report-image" onerror="parent.document.body.dataset.reportExecuted = 'yes'">
      </body></html>`,
  }))
  await page.goto("/samples/sample_demo/reports/report_demo")
  const frame = page.getByTitle("sample_demo saved report")
  await expect(frame).toHaveAttribute("sandbox", "allow-same-origin")
  await expect(page.frameLocator("iframe").getByRole("heading", { name: "Synthetic report" })).toBeVisible()
  await expect.poll(() => frame.evaluate((element) => element.clientHeight)).toBeGreaterThan(900)
  expect(await page.locator("body").getAttribute("data-report-executed")).toBeNull()
  const initialHeight = await frame.evaluate((element) => element.clientHeight)
  await page.waitForTimeout(500)
  const finalHeight = await frame.evaluate((element) => element.clientHeight)
  expect(finalHeight - initialHeight).toBeLessThanOrEqual(4)
})
