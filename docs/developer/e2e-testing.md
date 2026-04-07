# E2E Testing

Browser-level UI regression tests live under `tests/e2e/` and use Playwright
against a dedicated Flask test server.

## What The Harness Covers

The current suite exercises the highest-risk user flows end to end:

- Login to dashboard
- Login to samples list, then open DNA findings
- Login to samples list, then open CNV detail
- Coverage links opening in a new tab
- DNA preview report rendering
- Override-blacklist action persistence

## How It Works

The Playwright server does not call the real FastAPI backend. Instead, it boots
the real Flask UI with stateful API stubs from `tests/e2e/fake_ui_api.py`.

That gives us:

- real Flask routing
- real Jinja rendering
- real UI JavaScript and modal behavior
- deterministic fixture data shaped like production collection documents

The dedicated launcher is `tests/e2e/app_server.py`.

## Run The Suite

Install Node dependencies first:

```bash
npm install
npx playwright install chromium
```

Run the browser suite:

```bash
npm run e2e
```

## Adding A New Flow

1. Add or extend fixture state in `tests/e2e/fake_ui_api.py`.
2. If the flow needs a preview-style template, add it under `tests/e2e/templates/`.
3. Add a Playwright spec in `tests/e2e/critical-flows.spec.js` or split into a new spec file if the flow is large.
4. Keep selectors user-facing when possible:

```js
await page.getByRole("link", { name: "SAMPLE_001" }).click();
await expect(page.getByText("Preview Report")).toBeVisible();
```

## Why We Use A Dedicated Test Server

The existing Flask unit/UI tests are fast and good at route-level assertions,
but browser flows need more:

- real redirects
- popups/new tabs
- modal confirmation flows
- full HTML rendering
- real client-side JavaScript execution

Playwright covers that gap without coupling the suite to a live MongoDB or API
stack.
