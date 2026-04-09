const { test, expect } = require("@playwright/test");

async function resetState(request) {
  const response = await request.post("/coyote3/__e2e__/reset");
  expect(response.ok()).toBeTruthy();
}

async function login(page) {
  await page.goto("/coyote3/login");
  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
  await page.locator('input[name="username"]').fill("admin@example.com");
  await page.locator('input[name="password"]').fill("Coyote3.Admin");
  await page.locator('form[name="form"] button[type="submit"]').click();
  await expect(page).toHaveURL(/\/coyote3\/dashboard\/?$/);
}

test.beforeEach(async ({ request }) => {
  await resetState(request);
});

test("login redirects to dashboard", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Total Samples", { exact: true })).toBeVisible();
});

test("login to samples list then open DNA findings", async ({ page }) => {
  await login(page);
  await page.goto("/coyote3/samples");
  await expect(page.getByText("Live Samples")).toBeVisible();
  await page.getByRole("link", { name: "SAMPLE_001" }).click();
  await expect(page).toHaveURL(/\/coyote3\/dna\/sample\/SAMPLE_001$/);
  await expect(page.getByText("SNVs/Indels")).toBeVisible();
  await expect(page.getByRole("link", { name: /^TP53$/ })).toBeVisible();
});

test("login to samples list then open CNV detail", async ({ page }) => {
  await login(page);
  await page.goto("/coyote3/samples");
  await page.getByRole("link", { name: "SAMPLE_001" }).click();
  await page.locator('a[href*="/cnv/"]').first().click();
  await expect(page).toHaveURL(/\/coyote3\/dna\/SAMPLE_001\/cnv\/cnv1$/);
  await expect(page.getByText("CNV Wall")).toBeVisible();
  await expect(page.getByText("ERBB2")).toBeVisible();
});

test("coverage link opens in a new tab", async ({ page }) => {
  await login(page);
  await page.goto("/coyote3/samples");
  await page.getByRole("link", { name: "SAMPLE_001" }).click();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("link", { name: "COVERAGE" }).click();
  const coveragePage = await popupPromise;
  await coveragePage.waitForLoadState("domcontentloaded");
  await expect(coveragePage).toHaveURL(/\/coyote3\/cov\/SAMPLE_001$/);
  await expect(coveragePage.getByText("Coverage Review")).toBeVisible();
  await expect(coveragePage.getByRole("link", { name: "Open DNA findings" })).toBeVisible();
});

test("preview report renders from DNA findings page", async ({ page }) => {
  await login(page);
  await page.goto("/coyote3/samples");
  await page.getByRole("link", { name: "SAMPLE_001" }).click();
  await page.getByRole("link", { name: "Preview Report" }).click();
  await expect(page).toHaveURL(/\/coyote3\/dna\/sample\/SAMPLE_001\/reports\/preview$/);
  await expect(page.getByRole("heading", { name: "DNA Preview Report" })).toBeVisible();
  await expect(page.getByText("Sample: SAMPLE_001")).toBeVisible();
});

test("override blacklist action persists on the variant page", async ({ page }) => {
  await login(page);
  await page.goto("/coyote3/samples");
  await page.getByRole("link", { name: "SAMPLE_001" }).click();
  await page.locator('a[href*="/var/"]').first().click();
  await expect(page).toHaveURL(/\/coyote3\/dna\/SAMPLE_001\/var\/v1$/);
  const overrideButton = page.locator('input[type="submit"][value="Override Blacklist"]');
  await expect(overrideButton).toBeVisible();
  await overrideButton.click();
  await expect(page.getByRole("heading", { name: "Override Blacklist" })).toBeVisible();
  await page.locator("#actionModalConfirm").click();
  await expect(
    page.locator('input[type="submit"][value="Remove Blacklist Override"]'),
  ).toBeVisible();
});
