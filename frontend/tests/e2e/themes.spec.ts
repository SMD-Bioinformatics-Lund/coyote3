import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test.use({ timezoneId: "Europe/Stockholm" })

test("a signed-in public-page refresh retains CSRF protection for UI settings", async ({ page }, testInfo) => {
  let token = "synthetic-public-csrf-1"
  let theme = "light"
  await installApiFixtures(page, (path, _url, route) => {
    if (path === "/api/v1/auth/whoami") return { json: {
      username: "synthetic-viewer", role: "user", roles: ["user"], permissions: [],
      csrf_token: token, ui_settings: { theme },
    } }
    if (path === "/api/v1/users/me/ui-settings") {
      if (route.request().headers()["x-csrf-token"] !== token) {
        return { status: 403, json: { error: "CSRF validation failed" } }
      }
      theme = route.request().postDataJSON().theme
      return { json: { status: "ok", ui_settings: { theme } } }
    }
    if (path === "/api/v1/public/assay-catalog/offerings") {
      return { json: { version: 1, header: "Synthetic catalog", offerings: [] } }
    }
  })
  await page.goto("/public/catalog")
  let saved = page.waitForResponse(response => response.url().endsWith("/users/me/ui-settings"))
  await page.getByRole("button", { name: "Theme: light. Switch to dark", exact: true }).click()
  expect((await saved).status()).toBe(200)
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.getByRole("banner").screenshot({ path: testInfo.outputPath("dark-navigation.png") })
  token = "synthetic-public-csrf-2"
  await page.reload()
  saved = page.waitForResponse(response => response.url().endsWith("/users/me/ui-settings"))
  await page.getByRole("button", { name: "Theme: dark. Switch to auto", exact: true }).click()
  expect((await saved).status()).toBe(200)
  expect(page.url()).toContain("/public/catalog")
  await expect(page.getByText(/CSRF validation failed/)).toHaveCount(0)
})

for (const theme of ["light", "dark"]) {
  test(`${theme} capability rings remain separated with visible tracks`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await installApiFixtures(page, (path) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "demo", role: "superuser", roles: ["superuser"], access_level: 100000,
        permissions: [], ui_settings: { theme },
      } }
      if (path.startsWith("/api/v1/dashboard/metrics/")) return { json: {
        panel_analysis_capabilities: ["CNV", "CNV_PROFILE", "COVERAGE", "HRD", "MSI", "PGX", "SNV", "TMB", "TRANSLOCATION", "FUSION", "QC"]
          .map((analysis_type, index) => ({ analysis_type, enabled: 8, reportable: index % 3 ? 8 : 0 })),
      } }
    })
    await page.goto("/")
    const tracks = page.locator(".panel-capability-track")
    await expect(tracks).toHaveCount(11)
    expect(await tracks.first().evaluate(element => getComputedStyle(element).filter)).toContain("drop-shadow")
    expect(await page.locator(".panel-capability-progress").first().evaluate(element => getComputedStyle(element).filter)).toContain("drop-shadow")
    const metrics = await tracks.evaluateAll((nodes) => {
      const canvas = document.createElement("canvas")
      canvas.width = canvas.height = 1
      const ctx = canvas.getContext("2d")!
      const luminance = (color: string) => {
        ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1)
        const channels = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map((value) => {
          const s = value / 255; return s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4
        })
        return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722
      }
      const track = luminance(getComputedStyle(nodes[0]).stroke)
      const background = luminance(getComputedStyle(nodes[0].closest(".chart-panel")!).backgroundColor)
      return {
        contrast: (Math.max(track, background) + .05) / (Math.min(track, background) + .05),
        rings: nodes.map((node) => ({ left: node.getBoundingClientRect().left, right: node.getBoundingClientRect().right })),
      }
    })
    expect(metrics.contrast).toBeGreaterThanOrEqual(3)
    for (let index = 1; index < metrics.rings.length; index++) {
      expect(metrics.rings[index].left - metrics.rings[index - 1].right).toBeGreaterThan(8)
    }
    await tracks.first().scrollIntoViewIfNeeded()
    await page.locator(".chart-panel").filter({ hasText: "Panel analysis capability" }).screenshot({ path: testInfo.outputPath(`${theme}-capability-rings.png`) })
  })
}

test("automatic theme follows local time and both controls persist the account preference", async ({ page }) => {
  const user = { username: "demo", roles: ["admin"], role: "admin", permissions: [], access_level: 99999,
    auth_type: ["local"], ui_settings: { theme: "auto", table_page_size: 50 } }
  let failSave = false
  await installApiFixtures(page, (path, _url, route) => {
    if (path === "/api/v1/auth/whoami") return { json: user }
    if (path === "/api/v1/auth/session") return { json: { user } }
    if (path === "/api/v1/users/me/ui-settings") {
      if (failSave) return { status: 500, json: { error: "Save unavailable" } }
      user.ui_settings = { ...user.ui_settings, ...route.request().postDataJSON() }
      return { json: { status: "ok", ui_settings: user.ui_settings } }
    }
  })
  await page.clock.install({ time: new Date("2026-10-19T18:59:50+02:00") })
  await page.goto("/")
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.clock.fastForward(30_000)
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.getByRole("button", { name: "Theme: auto. Switch to light", exact: true }).click()
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.reload()
  await expect(page.locator("html")).toHaveClass(/light/)
  await page.goto("/profile")
  const preference = page.getByRole("tablist", { name: "Theme preference" })
  await expect(preference.getByRole("tab", { name: "Light", exact: true })).toHaveAttribute("aria-selected", "true")
  await preference.getByRole("tab", { name: "Dark", exact: true }).click()
  await expect(page.getByRole("button", { name: "Theme: dark. Switch to auto", exact: true })).toBeVisible()
  await expect(page.locator("html")).toHaveClass(/dark/)
  await expect.poll(() => user.ui_settings.theme).toBe("dark")
  failSave = true
  await page.getByRole("button", { name: "Theme: dark. Switch to auto", exact: true }).click()
  await expect(page.getByRole("button", { name: "Theme: dark. Switch to auto", exact: true })).toBeVisible()
  await expect(page.locator("html")).toHaveClass(/dark/)
})

test("dark charts use readable axes, tooltips and clinical badge colors", async ({ page }, testInfo) => {
  await installApiFixtures(page, (path) => {
    if (path === "/api/v1/auth/whoami") return { json: { username: "demo", roles: ["admin"], role: "admin", permissions: [], access_level: 99999, ui_settings: { theme: "dark" } } }
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
