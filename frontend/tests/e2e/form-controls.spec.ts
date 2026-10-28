import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"] as const) {
  test(`native and shared fields use the same outlined surface in ${theme} mode`, async ({ page }, testInfo) => {
    const user = { username: "synthetic", firstname: "Synthetic", fullname: "Synthetic user",
      roles: ["sys_admin"], role: "sys_admin", permissions: [], auth_type: ["local"], ui_settings: { theme } }
    await page.setViewportSize({ width: theme === "light" ? 1440 : 390, height: 1000 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    await installApiFixtures(page, path => {
      if (path === "/api/v1/auth/whoami") return { json: user }
      if (path === "/api/v1/auth/session") return { json: { user } }
    })
    await page.goto("/profile")
    await expect(page.getByLabel("Display name", { exact: true })).toBeVisible()
    await expect(page.locator("html")).toHaveClass(new RegExp(theme))
    const actualInput = page.getByLabel("Display name", { exact: true })
    expect(await actualInput.evaluate(element => getComputedStyle(element).boxShadow)).toContain("inset")
    await page.screenshot({ path: testInfo.outputPath(`profile-fields-${theme}.png`), fullPage: true })

    // Exercise native controls with existing page utilities, without depending on
    // a route's particular schema or changing any saved resource.
    await page.evaluate(() => {
      const form = document.createElement("form")
      form.id = "synthetic-fields"
      for (const type of ["text", "email", "password", "search", "number", "date", "datetime-local", "url", "tel"]) {
        const input = document.createElement("input")
        input.type = type
        input.setAttribute("aria-label", `Synthetic ${type}`)
        input.className = "bg-muted border-0 rounded-none"
        form.appendChild(input)
      }
      form.insertAdjacentHTML("beforeend", `
        <select aria-label="Synthetic select" class="bg-muted border-0"><option>One</option></select>
        <textarea aria-label="Synthetic textarea" class="bg-muted border-0"></textarea>
        <input aria-label="Synthetic disabled" disabled>
        <input aria-label="Synthetic readonly" readonly>
        <input aria-label="Synthetic invalid" aria-invalid="true">
        <input aria-label="Synthetic checkbox" type="checkbox">
        <input aria-label="Synthetic hidden" type="hidden">
        <div class="rich-text-field form-control"><div role="textbox" aria-label="Synthetic rich text" contenteditable="true"></div></div>
      `)
      document.body.appendChild(form)
    })
    const results = await page.locator("#synthetic-fields").evaluate(form => {
      const probe = document.createElement("span")
      probe.style.setProperty("transition", "none", "important")
      form.appendChild(probe)
      const color = (token: string) => {
        probe.style.backgroundColor = `var(--${token})`
        return getComputedStyle(probe).backgroundColor
      }
      const fields = [...form.querySelectorAll("input:not([disabled],[readonly],[aria-invalid],[type=checkbox],[type=hidden]),select,textarea")]
      return {
        surface: color("field-surface"), muted: color("paper-inset"), invalid: color("destructive"),
        controls: fields.map(element => {
          const style = getComputedStyle(element)
          return { background: style.backgroundColor, border: style.borderTopWidth,
            radius: parseFloat(style.borderRadius), shadow: style.boxShadow, transition: style.transitionDuration }
        }),
        disabled: getComputedStyle(form.querySelector("[disabled]")!).backgroundColor,
        readonly: getComputedStyle(form.querySelector("[readonly]")!).backgroundColor,
        invalidBorder: getComputedStyle(form.querySelector("[aria-invalid]")!).borderTopColor,
        checkboxShadow: getComputedStyle(form.querySelector("[type=checkbox]")!).boxShadow,
        hiddenDisplay: getComputedStyle(form.querySelector("[type=hidden]")!).display,
        richTextShadow: getComputedStyle(form.querySelector(".rich-text-field")!).boxShadow,
        richTextInnerBorder: getComputedStyle(form.querySelector("[contenteditable]")!).borderTopWidth,
      }
    })
    expect(results.controls).toHaveLength(11)
    for (const control of results.controls) {
      expect(control.background).toBe(results.surface)
      expect(control.border).toBe("1px")
      expect(control.radius).toBeGreaterThan(0)
      expect(control.shadow).toContain("inset")
      expect(Math.max(...control.transition.split(",").map(value => Number.parseFloat(value)))).toBeLessThanOrEqual(0.001)
    }
    expect(results.disabled).toBe(results.muted)
    expect(results.readonly).toBe(results.muted)
    expect(results.invalidBorder).toBe(results.invalid)
    expect(results.checkboxShadow).not.toContain("inset")
    expect(results.hiddenDisplay).toBe("none")
    expect(results.richTextShadow).toContain("inset")
    expect(results.richTextInnerBorder).toBe("0px")
    await page.getByLabel("Synthetic text", { exact: true }).focus()
    expect(await page.getByLabel("Synthetic text", { exact: true }).evaluate(element => getComputedStyle(element).outlineStyle)).toBe("solid")
    await page.emulateMedia({ forcedColors: "active" })
    expect(await page.getByLabel("Synthetic text", { exact: true }).evaluate(element => getComputedStyle(element).boxShadow)).toBe("none")
  })
}
