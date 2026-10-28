import { readFile, stat } from "node:fs/promises"
import { resolve, sep } from "node:path"
import { expect, test } from "@playwright/test"

const site = resolve(import.meta.dirname, "../../../site")
const types: Record<string, string> = { html: "text/html", js: "text/javascript", css: "text/css", svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg", woff2: "font/woff2", json: "application/json" }

for (const theme of ["light", "dark"]) {
  for (const width of [1440, 390]) {
    test(`documentation reading path, reference return and diagram in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 })
      await page.addInitScript(value => localStorage.setItem("coyote3-docs-theme", value), theme)
      await page.route("**/docs-site/**", async route => {
        const pathname = decodeURIComponent(new URL(route.request().url()).pathname.slice("/docs-site/".length))
        let file = resolve(site, pathname)
        if (!file.startsWith(site + sep) && file !== site) return route.fulfill({ status: 404 })
        try {
          if ((await stat(file)).isDirectory()) file = resolve(file, "index.html")
          await route.fulfill({ body: await readFile(file), contentType: types[file.split(".").at(-1)!] || "application/octet-stream" })
        } catch {
          await route.fulfill({ status: 404, body: "Build the documentation before running this test." })
        }
      })
      await page.goto("/docs-site/user-guide/clinical-review-workflow/")
      await expect(page.getByRole("heading", { level: 1, name: "Clinical review workflow" })).toBeVisible()
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme)
      await expect(page.getByRole("navigation", { name: "Reading path", exact: true })).toContainText("1 of 2")
      expect(await page.locator(".docs-page-contents").getAttribute("open")).toBeNull()
      const menu = page.getByRole("button", { name: "Toggle documentation menu", exact: true })
      if (width === 390) {
        await menu.click()
        await expect(menu).toHaveAttribute("aria-expanded", "true")
      }
      const initialUrl = page.url()
      await page.locator(".docs-nav-group > summary").filter({ hasText: /^Review a sample$/ }).click()
      expect(page.url()).toBe(initialUrl)
      if (width === 390) {
        await menu.click()
        await expect(menu).toHaveAttribute("aria-expanded", "false")
      }
      const expand = page.getByRole("button", { name: "Expand diagram: Clinical review responsibilities and evidence", exact: true })
      await expand.click()
      const diagram = page.getByRole("dialog", { name: "Clinical review responsibilities and evidence" })
      await expect(diagram).toBeVisible()
      expect(await diagram.locator("img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath("diagram.png") })
      await page.keyboard.press("Escape")
      await expect(diagram).toHaveCount(0)
      await expect(expand).toBeFocused()
      const reference = page.getByRole("link", { name: "DNA clinical review", exact: true })
      await reference.click()
      await expect(page).toHaveURL(/\/user-guide\/dna-review\/$/)
      const back = page.locator("#docs-return-context").getByRole("link", { name: "Return to Clinical review workflow", exact: true })
      await expect(back).toBeVisible()
      await back.click()
      await expect(page).toHaveURL(/\/clinical-review-workflow\/#docs-reference-/)
      await expect(reference).toBeInViewport()
      await page.getByRole("navigation", { name: "Continue this task", exact: true }).getByRole("link", { name: /Preview and save the report/ }).click()
      await expect(page).toHaveURL(/\/application-guide\/#reports$/)
      await expect(page.locator("#reports")).toBeInViewport()
      await expect(page.locator(".rst-footer-buttons")).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await page.screenshot({ path: testInfo.outputPath("report-reading.png") })
      await page.goto("/docs-site/deployment/configuration-reference/")
      if (width === 390) await menu.click()
      for (const name of ["Environments and secrets", "Compose files and storage mounts"]) {
        const link = page.getByRole("navigation").getByRole("link", { name, exact: true })
        await expect(link).toBeVisible()
        const contrast = await link.evaluate(element => {
          const luminance = (color: string) => {
            const rgb = color.match(/[\d.]+/g)!.slice(0, 3).map(value => {
              const channel = Number(value) / 255
              return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4
            })
            return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
          }
          const foreground = luminance(getComputedStyle(element).color)
          const background = luminance(getComputedStyle(document.querySelector(".wy-nav-side")!).backgroundColor)
          return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05)
        })
        expect(contrast, `${name}: sidebar text contrast`).toBeGreaterThanOrEqual(4.5)
        await link.focus()
        await expect(link).toBeFocused()
      }
      await page.screenshot({ path: testInfo.outputPath("configuration-navigation.png") })
      for (const filename of ["clinical-review-flow", "runtime-topology", "assay-configuration-relationships", "report-generation-flow", "resource-setup-order", "application-architecture", "sample-readiness-checks", "query-policy-flow"]) {
        await page.goto(`/docs-site/assets/diagrams/${filename}.svg`)
        const overflow = await page.locator("svg > g > text").evaluateAll(elements => elements.flatMap(element => {
          const text = element as SVGGraphicsElement
          const box = text.getBBox()
          const card = text.parentElement!.querySelector("rect")!
          const right = Number(card.getAttribute("x")) + Number(card.getAttribute("width"))
          const bottom = Number(card.getAttribute("y")) + Number(card.getAttribute("height"))
          return box.x + box.width > right - 8 || box.y + box.height > bottom - 4 ? [text.textContent] : []
        }))
        expect.soft(overflow, `${filename}: labels must fit their cards`).toEqual([])
      }
    })
  }
}
