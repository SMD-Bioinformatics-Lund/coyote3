import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`verification position lists retain numeric types in ${theme} at ${width}px`, async ({ page }) => {
    const writes: unknown[] = []
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme },
      } }
      if (path === "/api/v1/resources/aspc/create_context") return { json: { form: { fields: {
        verification_samples: { label: "Verification Samples", data_type: "json", display_type: "jsoneditor", default: {} },
      } } } }
      if (path === "/api/v1/resources/aspc" && route.request().method() === "POST") {
        writes.push(route.request().postDataJSON())
        return { json: { aspc_id: "synthetic-config" } }
      }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/aspc/create")
    for (const [index, sample, text] of [[0, "SYNTHETIC_A", "[101, 202]"], [1, "SYNTHETIC_B", "[303, 404]"]] as const) {
      await page.getByText("Add entry", { exact: true }).click()
      await page.getByPlaceholder("Key", { exact: true }).nth(index).fill(sample)
      await page.getByPlaceholder("Value", { exact: true }).nth(index).fill(text)
    }
    expect(writes).toEqual([])
    await page.getByRole("button", { name: "Save", exact: true }).first().click()
    await expect.poll(() => writes).toEqual([{ config: {
      verification_samples: { SYNTHETIC_A: [101, 202], SYNTHETIC_B: [303, 404] },
    } }])
  })
}
