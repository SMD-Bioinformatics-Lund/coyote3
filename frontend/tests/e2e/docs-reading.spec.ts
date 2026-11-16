import { readFile, stat } from "node:fs/promises"
import { resolve, sep } from "node:path"
import { expect, test } from "@playwright/test"

const site = resolve(import.meta.dirname, "../../../site")
const types: Record<string, string> = { html: "text/html", js: "text/javascript", css: "text/css", svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg", woff2: "font/woff2", json: "application/json" }

for (const theme of ["light", "dark"]) {
  for (const width of [1440, 390]) {
    test(`documentation reading path, reference return and diagram in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 })
      await page.addInitScript(value => localStorage.setItem("coyote4-docs-theme", value), theme)
      // External badge availability is separate from the local documentation contract.
      await page.route("https://img.shields.io/**", route => route.abort())
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
      await page.goto("/docs-site/")
      const article = page.locator('[itemprop="articleBody"]')
      await expect(article.locator("ul").first().getByRole("listitem")).toHaveCount(8)
      for (const name of ["Review and report a sample", "Configure an assay", "Install at a center", "Change the code"]) {
        await expect(article.getByRole("link", { name, exact: true })).toBeVisible()
      }
      await expect(page.locator(".docs-nav-section-label")).toHaveText([
        "Review samples", "Configure assays", "Install and operate", "Integrate pipelines",
        "Package guides", "Develop and validate", "Reference",
      ])
      await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1)
      await page.screenshot({ path: testInfo.outputPath("start-here.png") })
      await page.evaluate(() => sessionStorage.setItem("coyote4.docs.reference-trail", JSON.stringify([{
        from: new URL("/docs-site/reference/clinical-concepts/", location.href).href,
        to: "/docs-site/user-guide/clinical-review-workflow/", label: "A previous task",
      }])))
      await article.getByRole("link", { name: "Review and report a sample", exact: true }).click()
      await expect(page.locator("#docs-return-context")).toBeHidden()
      await expect(page.getByRole("heading", { level: 1, name: "Clinical review workflow" })).toBeVisible()
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme)
      await expect(page.getByRole("navigation", { name: "Reading path", exact: true })).toHaveCount(0)
      expect(await page.locator(".docs-page-contents").getAttribute("open")).toBeNull()
      expect(await article.locator("h1").evaluate(heading =>
        Boolean(heading.compareDocumentPosition(document.querySelector(".docs-reading-tools")!) & Node.DOCUMENT_POSITION_FOLLOWING)
      )).toBe(true)
      expect((await article.boundingBox())!.width).toBeLessThanOrEqual(820)
      const paragraphStyle = await article.locator("p").filter({ hasText: /^Clinical review progresses/ }).evaluate(element => {
        const style = getComputedStyle(element)
        return { font: parseFloat(style.fontSize), line: parseFloat(style.lineHeight) }
      })
      expect(paragraphStyle.font).toBeGreaterThanOrEqual(16)
      expect(paragraphStyle.line / paragraphStyle.font).toBeGreaterThanOrEqual(1.6)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      const menu = page.getByRole("button", { name: "Toggle documentation menu", exact: true })
      if (width === 390) {
        await menu.click()
        await expect(menu).toHaveAttribute("aria-expanded", "true")
      }
      const initialUrl = page.url()
      await page.locator(".docs-nav-group > summary").filter({ hasText: /^Review reference$/ }).click()
      expect(page.url()).toBe(initialUrl)
      if (width === 390) {
        await menu.click()
        await expect(menu).toHaveAttribute("aria-expanded", "false")
      }
      const expand = page.getByRole("button", { name: "Expand diagram: Clinical review responsibilities and evidence", exact: true })
      await expect(expand).toBeHidden()
      await page.getByText("View review responsibilities and saved evidence", { exact: true }).click()
      await expand.click()
      const diagram = page.getByRole("dialog", { name: "Clinical review responsibilities and evidence" })
      await expect(diagram).toBeVisible()
      expect(await diagram.locator("img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath("diagram.png") })
      await page.keyboard.press("Escape")
      await expect(diagram).toHaveCount(0)
      await expect(expand).toBeFocused()
      await page.emulateMedia({ media: "print" })
      await expect(page.locator(".wy-nav-side")).toBeHidden()
      await expect(page.locator(".docs-reading-tools")).toBeHidden()
      await expect(page.getByRole("heading", { level: 1, name: "Clinical review workflow" })).toBeVisible()
      expect(await article.evaluate(element => getComputedStyle(element).color)).toBe("rgb(64, 64, 64)")
      const printed = await page.pdf({ path: testInfo.outputPath("clinical-guide.pdf"), preferCSSPageSize: true })
      expect(printed.subarray(0, 5).toString()).toBe("%PDF-")
      await page.emulateMedia({ media: "screen" })
      const reference = page.getByRole("link", { name: "DNA clinical review", exact: true })
      await reference.click()
      await expect(page).toHaveURL(/\/user-guide\/dna-review\/$/)
      const back = page.locator("#docs-return-context").getByRole("link", { name: "Return to Clinical review workflow", exact: true })
      await expect(back).toBeVisible()
      await back.click()
      await expect(page).toHaveURL(/\/clinical-review-workflow\/#docs-reference-/)
      await expect(reference).toBeInViewport()
      await expect(page.getByRole("navigation", { name: "Continue this task", exact: true })).toContainText("End of this guide")
      await article.getByRole("link", { name: "report preview and save controls", exact: true }).click()
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
      await page.goto("/docs-site/administration/assay-setup/")
      const procedure = page.locator("#step-by-step-add-a-new-assay")
      const history = page.locator("#current-versions-and-history")
      expect((await procedure.boundingBox())!.y).toBeLessThan((await history.boundingBox())!.y)
      await expect(page.locator('[itemprop="articleBody"] pre').filter({ hasText: "function cleanupPublishedSetupDrafts" })).toHaveCount(0)
      await page.locator(".docs-page-contents > summary").click()
      await expect(page.locator(".docs-page-contents").getByRole("link", { name: "3. Select scopes and environments", exact: true })).toBeVisible()
      await page.locator(".docs-page-contents > summary").click()
      await page.screenshot({ path: testInfo.outputPath("assay-setup-reading.png") })
      for (const filename of ["clinical-review-flow", "runtime-topology", "assay-configuration-relationships", "report-generation-flow", "resource-setup-order", "application-architecture", "sample-readiness-checks", "query-policy-flow"]) {
        await page.goto(`/docs-site/assets/diagrams/${filename}.svg`)
        const overflow = await page.locator("svg > g > text").evaluateAll(elements => elements.flatMap(element => {
          const text = element as SVGGraphicsElement
          if (!text.textContent?.trim()) return []
          const box = text.getBBox()
          const group = text.parentElement!
          if (["left", "right", "top", "bottom"].some(side => !group.hasAttribute(`data-${side}`))) {
            return [`Missing layout bounds for ${text.textContent}`]
          }
          const left = Number(group.getAttribute("data-left"))
          const right = Number(group.getAttribute("data-right"))
          const top = Number(group.getAttribute("data-top"))
          const bottom = Number(group.getAttribute("data-bottom"))
          return box.x < left + 4 || box.y < top + 4 ||
            box.x + box.width > right - 8 || box.y + box.height > bottom - 4 ? [text.textContent] : []
        }))
        expect.soft(overflow, `${filename}: labels must fit their layout regions`).toEqual([])
      }
      for (const project of ["core", "api", "mongo", "client", "relay", "atlas", "demo", "frontend"]) {
        await page.goto(`/docs-site/packages/${project}/overview/`)
        await expect(article.getByRole("heading", { level: 1 })).toHaveCount(1)
        if (!["mongo", "frontend"].includes(project)) {
          const logo = article.locator('img[src$="-logo.svg"]')
          await expect(logo).toHaveCount(1)
          await expect(logo).toBeVisible()
          expect(await logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
        }
        const badges = page.locator('[itemprop="articleBody"] img[src^="https://img.shields.io/badge/"]')
        await expect(badges).toHaveCount(project === "frontend" ? 4 : 3)
        for (const source of await badges.evaluateAll(images => images.map(image => image.getAttribute("src")!))) {
          expect(new URL(source).searchParams.get("style")).toBe("flat")
        }
        await expect(page.locator('[itemprop="articleBody"] img[src*="logo="]')).toHaveCount(project === "frontend" ? 2 : 1)
      }
    })
  }
}
