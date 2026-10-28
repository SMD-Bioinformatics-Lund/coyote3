import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  test(`biomarker review preserves measured scores in ${theme} mode`, async ({ page }, testInfo) => {
    await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
    let assessment: { value: string; revision: number; assessed_by: string; assessed_at: string } | undefined
    let writes = 0
    const payload = () => ({ analysis_types: ["TMB"], biomarkers: [{
      _id: "synthetic-record", name: "Synthetic source",
      TMB: { value: 0, unit: "mut/Mb", clinical_assessment: assessment },
    }] })
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "synthetic.reviewer", roles: ["reviewer"], ui_settings: { theme },
        permissions: ["sample:view", "sample:edit:own"],
      } }
      if (path.endsWith("/edit-context")) return { json: {
        sample: { name: "SYNTHETIC", asp_category: "dna", environment: "testing", analysis_intents: ["somatic"] },
        analysis_sections: ["TMB"],
      } }
      if (path.endsWith("/biomarkers")) return { json: payload() }
      if (path.endsWith("/assessments/TMB")) {
        expect(route.request().method()).toBe("PATCH")
        expect(route.request().postDataJSON()).toEqual({ value: "HIGH", expected_revision: 0 })
        writes++
        assessment = { value: "HIGH", revision: 1, assessed_by: "synthetic.reviewer", assessed_at: "2026-10-28T12:00:00Z" }
        return { json: payload() }
      }
    })
    await page.goto("/samples/SYNTHETIC?tab=biomarkers")
    await expect(page.locator("html")).toHaveClass(new RegExp(theme))
    await expect(page.getByText("Not assessed", { exact: true })).toBeVisible()
    await expect(page.getByText("0 mut/Mb", { exact: false })).toBeVisible()
    await page.getByRole("button", { name: "Edit TMB assessment" }).click()
    const select = page.getByRole("combobox", { name: "TMB clinical assessment" })
    await expect(select).toBeEnabled()
    await select.focus()
    await page.keyboard.press("Enter")
    await page.getByRole("option", { name: "High", exact: true }).click()
    await page.getByRole("button", { name: "Save assessment" }).click()
    await expect(page.getByText("HIGH", { exact: true })).toBeVisible()
    await expect(page.getByText(/Saved by synthetic.reviewer/)).toBeVisible()
    expect(writes).toBe(1)
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await expect(page.getByRole("button", { name: "Edit TMB assessment" })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`biomarkers-${width}.png`), fullPage: true })
    }
  })
}
