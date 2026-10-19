import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const width of [1440, 390]) {
  test(`tooltips stay close to the pointer at viewport edges (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await installApiFixtures(page, (path) => path === "/api/v1/auth/whoami" ? { json: {
      username: "demo", role: "user", roles: ["user"], permissions: [],
      ui_settings: { theme: "dark" },
    } } : undefined)
    await page.goto("/public/catalog")
    const toggle = page.getByRole("button", { name: "Theme: dark. Switch to auto", exact: true })
    await expect(toggle).toBeVisible()
    const trigger = await toggle.boundingBox()
    const pointer = { x: trigger!.x + trigger!.width / 2, y: trigger!.y + trigger!.height / 2 }
    await page.mouse.move(pointer.x, pointer.y)
    const tooltip = page.getByRole("tooltip")
    await expect(tooltip).toContainText("Theme: dark. Switch to auto")
    await expect.poll(async () => {
      const box = await tooltip.boundingBox()
      if (!box) return null
      const expectedLeft = pointer.x + 14 + box.width <= width - 12
        ? pointer.x + 14 : pointer.x - box.width - 14
      return [Math.round(box.x - expectedLeft), Math.round(box.y - pointer.y - 14)]
    }).toEqual([0, 0])

    await page.evaluate(() => {
      const button = document.createElement("button")
      button.textContent = "Edge action"
      button.title = "Short hint"
      button.style.cssText = "position:fixed;right:12px;bottom:12px;width:100px;height:32px;z-index:100"
      document.body.append(button)
    })
    const edge = await page.getByRole("button", { name: "Edge action" }).boundingBox()
    const bottomPointer = { x: edge!.x + edge!.width / 2, y: edge!.y + edge!.height / 2 }
    await page.mouse.move(bottomPointer.x, bottomPointer.y)
    await expect(tooltip).toContainText("Short hint")
    await expect.poll(async () => {
      const box = await tooltip.boundingBox()
      return box && Math.abs(bottomPointer.x - box.x - box.width - 14) < 2
        && Math.abs(bottomPointer.y - box.y - box.height - 14) < 2
    }).toBe(true)
    await page.keyboard.press("Escape")
    await expect(tooltip).toHaveCount(0)
  })
}
