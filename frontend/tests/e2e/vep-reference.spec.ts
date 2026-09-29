import { expect, test } from "@playwright/test"
import { readFileSync } from "node:fs"
import { gunzipSync } from "node:zlib"
import { installApiFixtures } from "./support/api-fixtures"
import type { VepReference } from "../../src/pages/static/VepReferencePage"

const references: VepReference[] = gunzipSync(readFileSync("../api/config/bootstrap/reference/vep_metadata.seed.ndjson.gz")).toString().trim().split("\n").map(line => JSON.parse(line) as VepReference)

for (const width of [1440, 390]) {
  test(`VEP references and diagrams fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await installApiFixtures(page, path => {
      if (path === "/api/v1/auth/whoami") return { status: 401, json: { detail: "Not authenticated" } }
      if (path === "/api/v1/public/vep") return { json: { versions: references.map(row => row.vep_id).sort((a, b) => Number(b) - Number(a)) } }
      if (path.startsWith("/api/v1/public/vep/")) {
        const reference = references.find(row => row.vep_id === path.split("/").pop())
        return reference ? { json: reference } : { status: 404, json: { detail: "Not installed" } }
      }
    })
    await page.route("**/api/v1/public/vep/*/diagram", async route => {
      const release = new URL(route.request().url()).pathname.split("/").at(-2)
      const diagram = references.find(row => row.vep_id === release)?.consequence_diagram
      if (!diagram) return route.fulfill({ status: 404 })
      await route.fulfill({ contentType: diagram.mime_type, body: readFileSync(`../api/config/bootstrap/reference/vep_diagrams/${diagram.sha256}`) })
    })
    await page.goto("/about/vep")
    await expect(page.getByRole("heading", { name: "VEP Reference", exact: true })).toBeVisible()
    const image = page.getByRole("img", { name: /Ensembl 116 variant consequences/ })
    await expect(image).toBeVisible()
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await expect(page.getByLabel("VEP release")).toHaveValue("116")
    await page.screenshot({ path: `/tmp/coyote3-vep-${width}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    await page.getByLabel("Search VEP terms").fill("SO:0001583")
    await expect(page.getByRole("link", { name: "SO:0001583", exact: true })).toBeVisible()
    await page.getByText("missense_variant", { exact: true }).focus()
    await expect(page.getByText("Group: missense", { exact: true })).toBeVisible()
    await page.getByLabel("VEP release").selectOption("103")
    await expect(page).toHaveURL(/version=103/)
    const oldImage = page.getByRole("img", { name: /Ensembl 103 variant consequences/ })
    await expect.poll(() => oldImage.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await page.getByLabel("Search VEP terms").fill("")
    await page.getByRole("tab", { name: "Variant classes", exact: true }).click()
    await expect(page.getByRole("columnheader", { name: "Variant class", exact: true })).toBeVisible()
    await page.getByRole("tab", { name: "Cache sources", exact: true }).click()
    await expect(page.getByRole("heading", { name: "GRCh38", exact: true })).toBeVisible()
  })
}
