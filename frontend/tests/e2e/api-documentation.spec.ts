import { execFileSync } from "node:child_process"
import { resolve } from "node:path"
import { expect, test, type Locator, type Page } from "@playwright/test"

test.describe.configure({ mode: "default" })

let portal: { reference: string; explorer: string; schema: Record<string, unknown> }
const assets = new Map<string, { body: Buffer; contentType: string }>()

test.beforeAll(async ({ request }) => {
  // The pinned documentation bundles are downloaded once per worker. Allow setup
  // time for these large assets without extending individual interaction checks.
  test.setTimeout(120_000)
  const root = resolve(import.meta.dirname, "../../..")
  portal = JSON.parse(execFileSync(resolve(root, ".venv/bin/python"), ["-c", `
import asyncio
import json
from starlette.requests import Request
from coyote_api.app.main import create_api_app
app = create_api_app()
async def page(path):
    route = next(route for route in app.routes if getattr(route, "path", None) == path)
    response = await route.endpoint(Request({"type": "http", "root_path": "", "path": path}))
    return response.body.decode()
print(json.dumps({"reference": asyncio.run(page("/api/v1/redoc")),
                  "explorer": asyncio.run(page("/api/v1/docs")), "schema": app.openapi()}))
`], { cwd: root, env: { ...process.env, ENV_NAME: "test" }, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 }))
  for (const [file, contentType] of [
    ["redoc@2.5.3/bundles/redoc.standalone.js", "application/javascript"],
    ["swagger-ui-dist@5.32.15/swagger-ui-bundle.js", "application/javascript"],
    ["swagger-ui-dist@5.32.15/swagger-ui.css", "text/css"],
  ]) {
    const response = await request.get(`https://cdn.jsdelivr.net/npm/${file}`)
    expect(response.ok()).toBe(true)
    assets.set(file, { body: await response.body(), contentType })
  }
})

async function mockPortal(page: Page) {
  await page.route("https://cdn.jsdelivr.net/npm/**", route => {
    const asset = assets.get(route.request().url().split("/npm/")[1])
    return asset ? route.fulfill(asset) : route.abort()
  })
  await page.route("**/api/v1/openapi.json", route => route.fulfill({ json: portal.schema }))
  await page.route("**/api/v1/auth/whoami", route => route.fulfill({ status: 401, json: {} }))
  for (const [path, view] of [["docs", "explorer"], ["redoc", "reference"]] as const) {
    await page.route(`**/api/v1/${path}*`, route => route.fulfill({ contentType: "text/html", body: portal[view] }))
  }
}

async function expectReadable(locator: Locator) {
  const contrast = await locator.evaluate(element => {
    const canvas = document.createElement("canvas")
    canvas.width = canvas.height = 1
    const context = canvas.getContext("2d")!
    const ancestors: Element[] = []
    for (let node: Element | null = element; node; node = node.parentElement) ancestors.push(node)
    context.fillStyle = "white"
    context.fillRect(0, 0, 1, 1)
    for (const node of ancestors.reverse()) {
      context.fillStyle = getComputedStyle(node).backgroundColor
      context.fillRect(0, 0, 1, 1)
    }
    const background = [...context.getImageData(0, 0, 1, 1).data]
    context.fillStyle = getComputedStyle(element).color
    context.fillRect(0, 0, 1, 1)
    const foreground = [...context.getImageData(0, 0, 1, 1).data]
    const luminance = (rgba: number[]) => {
      const rgb = rgba.slice(0, 3).map(value => {
        const channel = value / 255
        return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4
      })
      return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
    }
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
    return (values[0] + .05) / (values[1] + .05)
  })
  expect(contrast).toBeGreaterThanOrEqual(4.5)
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1920, 1440, 390]) {
    for (const view of ["reference", "explorer"] as const) {
      test(`API ${view} is readable and responsive in ${theme} at ${width}px`, async ({ page }, testInfo) => {
        await page.emulateMedia({ colorScheme: theme })
        await page.setViewportSize({ width, height: 1000 })
        await mockPortal(page)
        const path = view === "reference" ? "/api/v1/redoc" : "/api/v1/docs"
        const errors: string[] = []
        page.on("pageerror", error => errors.push(error.message))
        await page.goto(path)
        await expect(page.locator("#docs-loading")).toBeHidden()
        await expect(page.locator("#docs-error")).toBeHidden()
        if (view === "explorer") {
          await expectReadable(page.locator('.opblock-tag[data-tag="Authentication"] a'))
          await page.getByRole("navigation", { name: "Endpoint groups" })
            .getByRole("link", { name: /^Authentication/ }).click()
          const operation = page.locator(".opblock").filter({ hasText: "/api/v1/auth/whoami" })
          await operation.locator(".opblock-summary-control").click()
          await expectReadable(operation.locator(".opblock-summary-path"))
          await expectReadable(operation.locator(".opblock-description-wrapper p").first())
          await expectReadable(operation.locator(".opblock-section-header h4").first())
          await expectReadable(operation.getByText("No parameters", { exact: true }))
          await expectReadable(operation.locator("thead .response-col_links"))
          await expectReadable(operation.getByText("No links", { exact: true }).first())
          await expect(operation.getByRole("button", { name: "Try it out" })).toBeVisible()
        } else {
          const selector = page.getByRole("combobox", { name: "API resource", exact: true })
          await selector.selectOption("Authentication")
          await expect(page.locator("#docs-loading")).toBeHidden()
          const authentication = page.locator("#api-renderer table").filter({ hasText: "When changing data" })
          await expectReadable(authentication.getByRole("columnheader", { name: "Client", exact: true }))
          await expectReadable(authentication.getByRole("cell", { name: "Your Coyote4 session cookie", exact: true }))
          await expectReadable(page.locator("#api-renderer [role=tab].tab-error").first())
          await expectReadable(page.locator("#api-renderer .redoc-json .token.string").first())
          await expectReadable(page.getByRole("tab", { name: "Payload", exact: true }).first())
          const responseSample = page.locator('#api-renderer div:has(> [data-rttabs="true"])')
            .filter({ has: page.getByRole("heading", { name: "Response samples", exact: true }) }).first()
          await responseSample.scrollIntoViewIfNeeded()
          const errorTab = responseSample.getByRole("tab", { name: "401", exact: true })
          await errorTab.click()
          await expect(errorTab).toHaveAttribute("aria-selected", "true")
          await expectReadable(errorTab)
          await errorTab.press("ArrowLeft")
          await expect(responseSample.getByRole("tab", { name: "200", exact: true }))
            .toHaveAttribute("aria-selected", "true")
          const copy = responseSample.getByRole("button", { name: "Copy", exact: true })
          await copy.focus()
          await expect(copy).toBeFocused()
          await page.screenshot({ path: testInfo.outputPath("response-samples.png") })
          await selector.selectOption("Clinical Samples")
          await expect(selector).toHaveValue("Clinical Samples")
          await expect(page.locator("#docs-loading")).toBeHidden()
          await expect(page.locator("#api-renderer")).toContainText("Clinical Samples")
          await page.locator('#api-renderer a[href^="#tag/Clinical-Samples/operation/"]').first().click()
          await expect(selector).toHaveValue("Clinical Samples")
          // Scroll-spy updates must not override an explicitly selected resource.
          await page.evaluate(() => { location.hash = "tag/Authentication" })
          await page.reload()
          await expect(page.locator("#docs-loading")).toBeHidden()
          await expect(selector).toHaveValue("Clinical Samples")
          await selector.selectOption("Admin: Assays & Gene Lists")
          await expect(page.locator("#docs-loading")).toBeHidden()
          expect(new URL(page.url()).searchParams.get("resource")).toBe("Admin: Assays & Gene Lists")
          await expect(selector).toHaveValue("Admin: Assays & Gene Lists")
          await page.locator('#api-renderer a[href="#tag/Admin:-Assays-and-Gene-Lists"]').click()
          await page.reload()
          await expect(page.locator("#docs-loading")).toBeHidden()
          await expect(selector).toHaveValue("Admin: Assays & Gene Lists")
          await selector.selectOption("Authentication")
          await expect(page.locator("#docs-loading")).toBeHidden()
          // A single resource must not mount the entire API and its nested schema tables.
          expect(await page.locator("#api-renderer *").count()).toBeLessThan(15_000)
          await page.getByRole("button", { name: theme === "dark" ? "Use light theme" : "Use dark theme" }).click()
          await expect(page.locator("#docs-loading")).toBeHidden()
          await expectReadable(authentication.getByRole("cell", { name: "Your Coyote4 session cookie", exact: true }))
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        expect(errors).toEqual([])
        await page.locator("#api-content").scrollIntoViewIfNeeded()
        await page.screenshot({ path: testInfo.outputPath("api-documentation.png") })
        const selectedTheme = theme === "dark" ? "light" : "dark"
        if (view === "explorer") {
          await page.getByRole("button", { name: theme === "dark" ? "Use light theme" : "Use dark theme" }).click()
        }
        expect(await page.evaluate(() => localStorage.getItem("coyote4-docs-theme"))).toBe(selectedTheme)
        await page.reload()
        await expect(page.locator("#docs-loading")).toBeHidden()
        expect(await page.locator("html").evaluate(element => element.classList.contains("dark")))
          .toBe(selectedTheme === "dark")
        await expect(page.getByRole("button", { name: selectedTheme === "dark" ? "Use light theme" : "Use dark theme" }))
          .toHaveAttribute("aria-pressed", String(selectedTheme === "dark"))
      })
    }
  }
}

test("explorer navigation works before a slow browser session check completes", async ({ page }) => {
  await mockPortal(page)
  let releaseSession!: () => void
  const sessionReady = new Promise<void>(resolve => { releaseSession = resolve })
  await page.route("**/api/v1/auth/whoami", async route => {
    await sessionReady
    await route.fulfill({ json: { username: "fixture-user", csrf_token: "fixture-csrf" } })
  })
  try {
    await page.goto("/api/v1/docs")
    await expect(page.locator("#docs-loading")).toBeHidden()
    const navigation = page.getByRole("navigation", { name: "Endpoint groups" })
    const resource = navigation.getByRole("link", { name: /^Clinical Samples/ })
    const heading = page.locator('.opblock-tag[data-tag="Clinical Samples"]')
    await expect(heading).toHaveAttribute("data-is-open", "true")
    await heading.getByRole("button", { name: "Collapse operation", exact: true }).click()
    await expect(heading).toHaveAttribute("data-is-open", "false")
    await resource.click()
    await expect(heading).toHaveAttribute("data-is-open", "true")
    await expect(heading).toBeInViewport()
    await expect(resource).toHaveAttribute("aria-current", "location")
    expect(new URL(page.url()).hash).toBe("#/Clinical%20Samples")
    await page.getByPlaceholder("Filter by tag").fill("Authentication")
    await expect(heading).toHaveCount(0)
    await resource.click()
    await expect(heading).toBeInViewport()
    await expect(page.getByPlaceholder("Filter by tag")).toHaveValue("")
    await page.setViewportSize({ width: 390, height: 844 })
    await resource.focus()
    await page.keyboard.press("Enter")
    await expect(heading).toBeInViewport()
  } finally {
    releaseSession()
  }
  await expect(page.locator("#csrf-token")).toHaveValue("fixture-csrf")
  await page.reload()
  await expect(page.locator('.opblock-tag[data-tag="Clinical Samples"]')).toHaveAttribute("data-is-open", "true")
})

test("explorer attaches session CSRF only to cookie-authenticated changes", async ({ page }) => {
  await mockPortal(page)
  await page.route("**/api/v1/auth/whoami", route => route.fulfill({
    json: { username: "fixture-user", csrf_token: "fixture-csrf" },
  }))
  await page.route("**/api/v1/auth/sessions/current", route => route.fulfill({ json: { status: "ok" } }))
  await page.goto("/api/v1/docs")
  await page.getByRole("navigation", { name: "Endpoint groups" })
    .getByRole("link", { name: /^Authentication/ }).click()
  const operation = page.locator(".opblock-delete").filter({ hasText: "/api/v1/auth/sessions/current" })
  await operation.locator(".opblock-summary-control").click()
  await operation.getByRole("button", { name: "Try it out" }).click()
  const cookieRequest = page.waitForRequest(request => request.method() === "DELETE")
  await operation.getByRole("button", { name: "Execute", exact: true }).click()
  expect((await cookieRequest).headers()["x-csrf-token"]).toBe("fixture-csrf")

  await page.locator(".scheme-container").getByRole("button", { name: "Authorize" }).click()
  const bearer = page.locator(".auth-container").filter({ hasText: "BearerAuth" })
  await bearer.locator("input").fill("fixture-bearer")
  await bearer.getByRole("button", { name: "Apply credentials", exact: true }).click()
  await bearer.getByRole("button", { name: "Close", exact: true }).click()
  const bearerRequest = page.waitForRequest(request => request.method() === "DELETE")
  await operation.getByRole("button", { name: "Execute", exact: true }).click()
  const headers = await (await bearerRequest).allHeaders()
  expect(headers.authorization).toBe("Bearer fixture-bearer")
  expect(headers["x-csrf-token"]).toBeUndefined()
  expect(await page.evaluate(() => Object.values(localStorage))).not.toContain("fixture-bearer")
})


test("explorer shell stays usable while the vendor stylesheet is loading", async ({ page }) => {
  await mockPortal(page)
  let releaseStyles!: () => void
  const stylesReady = new Promise<void>(resolve => { releaseStyles = resolve })
  await page.route("**/swagger-ui.css", async route => {
    await stylesReady
    await route.fulfill(assets.get("swagger-ui-dist@5.32.15/swagger-ui.css")!)
  })
  try {
    await page.goto("/api/v1/docs", { waitUntil: "domcontentloaded" })
    await expect(page.getByRole("heading", { name: "Coyote4 API", exact: true })).toBeVisible()
    await expect(page.locator("#docs-loading")).toBeVisible()
    const toggle = page.getByRole("button", { name: /Use (dark|light) theme/ })
    const pressed = await toggle.getAttribute("aria-pressed")
    await toggle.click()
    await expect(toggle).toHaveAttribute("aria-pressed", pressed === "true" ? "false" : "true")
  } finally {
    releaseStyles()
  }
  await expect(page.locator("#docs-loading")).toBeHidden()
  await expect(page.locator("#docs-error")).toBeHidden()
  await expect(page.getByRole("navigation", { name: "Endpoint groups" }).getByRole("link").first()).toBeVisible()
})

test("a failed explorer stylesheet offers the OpenAPI contract", async ({ page }) => {
  await mockPortal(page)
  await page.route("**/swagger-ui.css", route => route.abort())
  await page.goto("/api/v1/docs")
  await expect(page.locator("#docs-error")).toBeVisible()
  await expect(page.locator("#docs-loading")).toBeHidden()
  await expect(page.locator("#docs-error").getByRole("link")).toHaveAttribute("href", "/api/v1/openapi.json")
})
