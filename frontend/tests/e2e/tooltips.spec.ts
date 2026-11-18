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

for (const width of [1440, 390]) {
  test(`a clicked or keyboard-focused hint cannot follow the pointer across the page (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await installApiFixtures(page)
    await page.goto("/public/catalog")
    const toggle = page.getByRole("button", { name: /^Theme:/ })
    await toggle.click()
    await page.mouse.move(width / 2, 300)
    const tooltip = page.getByRole("tooltip")
    // It may dismiss on pointer exit or remain by the focused control, never at the distant cursor.
    await expect.poll(async () => {
      if (await tooltip.count() === 0) return true
      const hint = await tooltip.boundingBox()
      const control = await toggle.boundingBox()
      return Boolean(hint && control && hint.y >= control.y && hint.y - control.y - control.height < 40
        && hint.x + hint.width >= control.x && hint.x <= control.x + control.width)
    }).toBe(true)

    await toggle.evaluate(button => (button as HTMLElement).blur())
    await toggle.focus()
    await expect(tooltip).toBeVisible()
    const anchored = await tooltip.boundingBox()
    await page.mouse.move(width / 2 + 40, 350)
    await expect.poll(() => tooltip.boundingBox()).toEqual(anchored)
    await page.keyboard.press("Escape")
    await expect(tooltip).toHaveCount(0)
  })
}

test("login shows icon hints without repeating labels or exposing typed values", async ({ page }) => {
  await installApiFixtures(page, path => path === "/api/v1/auth/providers"
    ? { json: { providers: ["local"] } } : undefined)
  await page.goto("/login")
  const tooltip = page.getByRole("tooltip")
  const signIn = page.getByRole("button", { name: "Sign in", exact: true })
  await expect(signIn).toBeDisabled()
  await signIn.hover()
  await expect(tooltip).toHaveCount(0)
  await expect(signIn).toBeDisabled()

  const password = page.getByLabel("Password", { exact: true })
  await password.fill("synthetic-secret")
  await password.hover()
  await expect(tooltip).toHaveCount(0)
  const reveal = page.getByRole("button", { name: "Show password", exact: true })
  await reveal.hover()
  await expect(tooltip).toContainText("Show password")
  await expect(tooltip).not.toContainText("synthetic-secret")
  await reveal.click()
  await expect(tooltip).toContainText("Hide password")
  await page.getByRole("link", { name: "Forgot password?", exact: true }).hover()
  await expect(tooltip).toHaveCount(0)
})
