import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test.use({ timezoneId: "Europe/Stockholm" })

test("automatic theme follows local time and manual preference persists", async ({ page }) => {
  await installApiFixtures(page)
  await page.clock.install({ time: new Date("2026-10-19T18:59:50+02:00") })
  await page.goto("/")
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.clock.fastForward(30_000)
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption("light")
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.reload()
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.emulateMedia({ colorScheme: "dark" })
  await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption("system")
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.emulateMedia({ colorScheme: "light" })
  await expect(page.locator("html")).toHaveClass(/light/)
})

test("dark charts use readable axes, tooltips and clinical badge colors", async ({ page }, testInfo) => {
  await installApiFixtures(page, (path) => {
    if (path.startsWith("/api/v1/dashboard/metrics/")) return { json: {
      total_samples: 8, analysed_samples: 5, pending_samples: 3,
      sample_stats: { omics_layers: { dna: 6, rna: 2 }, profiles: { production: 8 } },
      panel_gene_stats_grouped: { demo: [{ asp_id: "demo", display_name: "Demo assay", covered_genes_count: 9, germline_genes_count: 1 }] },
    } }
  })
  await page.addInitScript(() => localStorage.setItem("vite-ui-theme", "dark"))
  await page.goto("/")
  await expect(page.locator(".recharts-cartesian-axis-tick-value").first()).toBeVisible()
  await page.locator(".recharts-pie-sector").first().dispatchEvent("mouseover")
  await expect(page.locator(".recharts-default-tooltip").filter({ visible: true }).first()).toBeVisible()
  const results = await page.evaluate(() => {
    const canvas = document.createElement("canvas")
    canvas.width = canvas.height = 1
    const ctx = canvas.getContext("2d")!
    const luminance = (color: string) => {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1)
      const channels = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map((v) => {
        const s = v / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      })
      return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722
    }
    const probe = document.createElement("span"); document.body.appendChild(probe)
    const token = (key: string) => { probe.style.color = `var(--${key})`; return getComputedStyle(probe).color }
    const ratio = (a: string, b: string) => {
      const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05)
    }
    const pairs = ["info", "success", "warning", "danger", "cnv-gain", "cnv-loss", "somatic", "germline"]
    const values = pairs.map((name) => ({ name, contrast: ratio(token(`badge-${name}-foreground`), token(`badge-${name}-background`)) }))
    for (const background of ["primary", "brand-start", "brand-end"]) {
      values.push({ name: background, contrast: ratio(token("primary-foreground"), token(background)) })
    }
    const axis = document.querySelector(".recharts-cartesian-axis-tick-value")!
    values.push({ name: "chart axis", contrast: ratio(getComputedStyle(axis).fill, token("paper-raised")) })
    const tooltip = [...document.querySelectorAll<HTMLElement>(".recharts-default-tooltip")].find((node) => node.checkVisibility({ visibilityProperty: true }))!
    values.push({ name: "tooltip", contrast: ratio(getComputedStyle(tooltip).color, getComputedStyle(tooltip).backgroundColor) })
    probe.remove(); return values
  })
  for (const { name, contrast } of results) expect(contrast, name).toBeGreaterThanOrEqual(4.5)
  await page.screenshot({ path: testInfo.outputPath("dark-dashboard.png"), fullPage: true })
  await page.locator(".chart-panel").filter({ hasText: "Gene coverage per assay" }).screenshot({ path: testInfo.outputPath("dark-chart.png") })
})
