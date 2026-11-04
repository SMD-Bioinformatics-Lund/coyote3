import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

const thresholds = [
  { key: "min_alt_reads", label: "Min Alt Reads", type: "int", value: 5, next: 6 },
  { key: "min_depth", label: "Min Depth", type: "int", value: 100, next: 101 },
  { key: "min_freq", label: "Min AF", type: "float", value: 0.02, next: 0.021 },
  { key: "max_freq", label: "Max AF", type: "float", value: 1, next: 0.999 },
  { key: "max_control_freq", label: "Max Control AF", type: "float", value: 0.05, next: 0.051 },
  { key: "max_popfreq", label: "Max Population AF", type: "float", value: 0.01, next: 0.011 },
]

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`filter arrows preserve fractional values in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    let saved: unknown
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme },
      } }
      if (path === "/api/v1/resources/aspc/create_context") return { json: { form: { fields: {
        filters: { label: "Clinical filters", data_type: "json", display_type: "filters-structured",
          groups: [{ title: "SNV thresholds", fields: thresholds.map(field => ({
            key: `somatic.snv.${field.key}`, label: field.label, type: field.type, default: field.value,
          })) }, { title: "CNV thresholds", fields: [{
            key: "somatic.cnv.cnv_loss_cutoff", label: "Loss cutoff", type: "float", step: 0.01, default: -0.3,
          }] }],
        },
      } } } }
      if (path === "/api/v1/resources/aspc" && route.request().method() === "POST") {
        saved = route.request().postDataJSON()
        return { json: { aspc_id: "synthetic-config" } }
      }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/aspc/create")
    for (const field of thresholds) {
      const input = page.getByRole("spinbutton", { name: new RegExp(`${field.label}$`) })
      await expect(input).toHaveAttribute("step", field.type === "int" ? "1" : "0.001")
      await input.press(field.key === "max_freq" ? "ArrowDown" : "ArrowUp")
      await expect(input).toHaveValue(String(field.next))
    }
    const cutoff = page.getByRole("spinbutton", { name: "Loss cutoff", exact: true })
    await expect(cutoff).toHaveAttribute("step", "0.01")
    await cutoff.press("ArrowUp")
    await expect(cutoff).toHaveValue("-0.29")
    await page.screenshot({ path: testInfo.outputPath(`filter-steps-${theme}-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save", exact: true }).first().click()
    await expect.poll(() => saved).toEqual({ config: { filters: { somatic: {
      snv: Object.fromEntries(thresholds.map(field => [field.key, field.next])),
      cnv: { cnv_loss_cutoff: -0.29 },
    } } } })
  })
}
