import { readFileSync } from "node:fs"
import { expect, test } from "@playwright/test"

const html = readFileSync(new URL("../../../deploy/compose/nginx/error-pages/unavailable.html", import.meta.url), "utf8")

for (const colorScheme of ["light", "dark"] as const) {
  for (const width of [390, 1440]) {
    test(`standalone Nginx error page in ${colorScheme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ colorScheme, reducedMotion: "reduce" })
      let attempts = 0
      const requests: string[] = []
      page.on("request", request => requests.push(request.url()))
      await page.route("**/unavailable-test?context=synthetic", async route => {
        attempts += 1
        await route.fulfill({ status: 503, contentType: "text/html; charset=utf-8", body: html })
      })
      const response = await page.goto("/unavailable-test?context=synthetic")
      expect(response?.status()).toBe(503)
      await expect(page.getByRole("heading", { name: "Service temporarily unavailable" })).toBeVisible()
      await expect(page.getByText("COYOT3", { exact: true })).toBeVisible()
      await page.keyboard.press("Tab")
      const retry = page.getByRole("link", { name: "Try again" })
      await expect(retry).toBeFocused()
      expect(await retry.evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe("none")
      await page.keyboard.press("Enter")
      await expect.poll(() => attempts).toBe(2)
      await expect(page).toHaveURL(/\/unavailable-test\?context=synthetic$/)
      expect(requests.every(url => url.endsWith("/unavailable-test?context=synthetic"))).toBe(true)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      const panel = page.getByRole("region", { name: "Service temporarily unavailable" })
      expect(await panel.evaluate(el => getComputedStyle(el).boxShadow)).not.toBe("none")
      await page.screenshot({ path: testInfo.outputPath(`nginx-error-${colorScheme}-${width}.png`), fullPage: true })
      await page.emulateMedia({ forcedColors: "active" })
      expect(await panel.evaluate(el => getComputedStyle(el).boxShadow)).toBe("none")
      await expect(retry).toBeVisible()
    })
  }
}
