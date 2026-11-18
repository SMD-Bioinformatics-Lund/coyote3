import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const reducedMotion of ["no-preference", "reduce"] as const) {
  test(`loading remains labelled and respects ${reducedMotion} motion`, async ({ page }, testInfo) => {
    await page.emulateMedia({ reducedMotion, colorScheme: reducedMotion === "reduce" ? "dark" : "light" })
    let release!: () => void
    const pending = new Promise<void>(resolve => { release = resolve })
    await installApiFixtures(page, async path => {
      if (path === "/api/v1/auth/whoami") await pending
    })

    try {
      await page.goto("/admin/users")
      const loading = page.getByRole("status", { name: "Loading", exact: true })
      await expect(loading).toBeVisible()
      await expect(loading).toHaveText("Loading")
      const emblem = loading.locator('img[aria-hidden="true"]')
      await expect.poll(() => emblem.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
      if (reducedMotion === "reduce") {
        await expect(emblem).toHaveCSS("animation-name", "none")
      } else {
        expect(await emblem.evaluate(image => getComputedStyle(image).animationName)).not.toBe("none")
      }
      await page.screenshot({ path: testInfo.outputPath("loading.png") })
    } finally {
      release()
    }
    await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible()
    await expect(page.locator(".global-loader")).toHaveCount(0)
  })
}
