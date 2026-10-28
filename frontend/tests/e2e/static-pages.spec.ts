import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  test(`About and Contact use separate raised cards in ${theme} mode`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: theme === "light" ? 1440 : 390, height: 1000 })
    await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
    const information = {
      organization: { name: "Synthetic Training Center", department: "Demonstration",
        address: "1 Example Road", description: "Synthetic center information." },
      application: { version: "4.0.0", sdk_version: "1.0.0", client_sdk_version: "1.0.0", environment: "testing" },
      databases: { primary: "synthetic", knowledgebases: { oncokb: "https://example.org" } },
      references: { vep_metadata: ["103"], sample_database_versions: { assembly: ["GRCh38"] } },
      software: { pipelines: { SyntheticPipeline: "1.0" } },
      support: { primary_email: "support@example.org", urgent_phone: "+46000000000" },
      contacts: [{ label: "Platform support", role: "Application support", description: "Synthetic support channel.",
        people: [{ name: "Training Team", email: "team@example.org" }] }],
      hours: [{ label: "Service desk", value: "Weekdays 08:00–16:00" }],
      links: [{ label: "Documentation", url: "/docs-site/", icon: "docs" }],
    }
    await installApiFixtures(page, path => {
      if (path === "/api/v1/auth/whoami") return { status: 401, json: {} }
      if (path === "/api/v1/public/about" || path === "/api/v1/public/contact") return { json: information }
    })
    await page.goto("/about")
    await expect(page.locator("html")).toHaveClass(new RegExp(theme))
    await expect(page.getByText("SyntheticPipeline")).toBeVisible()
    const versions = page.getByRole("region", { name: "Reference and software versions" })
    await expect(versions.locator(".static-info-card")).toHaveCount(4)
    const cards = await page.locator(".static-info-card").evaluateAll(elements => elements.map(element => {
      const style = getComputedStyle(element)
      return { shadow: style.boxShadow, radius: parseFloat(style.borderRadius) }
    }))
    expect(cards.length).toBeGreaterThan(4)
    for (const card of cards) {
      expect(card.shadow).not.toBe("none")
      expect(card.radius).toBeGreaterThan(0)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`about-cards-${theme}.png`), fullPage: true })

    await page.goto("/contact")
    const contact = page.getByRole("link", { name: /Training Team/ })
    await expect(contact).toHaveAttribute("href", "mailto:team@example.org")
    expect(await contact.evaluate(element => getComputedStyle(element).boxShadow)).not.toBe("none")
    await expect(page.getByText("Weekdays 08:00–16:00")).toBeVisible()
    await expect(page.getByRole("heading", { name: "Address" })).toBeVisible()
    const detailWidths = await page.getByRole("region", { name: "Center and service details" })
      .locator(".static-info-card").evaluateAll(elements => elements.map(element => element.getBoundingClientRect().width))
    for (const width of detailWidths) expect(width).toBeGreaterThan(250)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`contact-cards-${theme}.png`), fullPage: true })
  })
}
