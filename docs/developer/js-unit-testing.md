# JavaScript Unit Testing

Coyote3 ships a small set of vanilla-JS helpers in `coyote/static/js/`. They are
covered by Vitest unit tests under `tests/js/`, running in a jsdom environment.
This guide explains how to run them and how the tests are wired.

## Running

```bash
npm install        # one-time, installs vitest + jsdom
npm test           # one-shot run
npm run test:watch # watch mode
```

The Vitest config lives at [`tests/js/vitest.config.js`](../../tests/js/vitest.config.js).

## What is covered

| File under test | Test file |
|---|---|
| `coyote/static/js/api_client.js` | `tests/js/api_client.test.mjs` |
| `coyote/static/js/sortableTable.js` | `tests/js/sortableTable.test.mjs` |
| `coyote/static/js/pagination.js` | `tests/js/pagination.test.mjs` |

### `api_client.js`
Mocks `window.fetch` and verifies:
- URL construction (`/api/v1/...`, `COYOTE_API_BASE` override, trailing-slash stripping)
- Query string encoding and skipping of null/undefined/empty values
- JSON body serialization with correct `Content-Type`
- FormData passthrough (no JSON encoding)
- JSON vs text response parsing
- Error handling: status, payload, fallback message

### `sortableTable.js`
Builds a real `<table>` in jsdom, injects the script via a `<script>` element,
fires `DOMContentLoaded`, then clicks headers and asserts row order. Covers:
- Plain numeric sort (asc/desc)
- `chr:pos` chromosome sort
- `chr:start-end` range sort
- Mixed alphanumeric natural sort
- Relative time strings ("5 minutes ago", "a week ago")
- Sort arrow visibility toggling
- `data-nosort` opt-out

### `pagination.js`
Builds a `.pagination` wrapper, fires `DOMContentLoaded`, and exercises:
- No controls when row count is at or below the limit
- Initial page rendering (first slice visible)
- `nextPage()` / `prevPage()` navigation
- Prev/Next button visibility on first/last pages
- Out-of-range page requests are ignored
- Calling helpers with an unknown table id is a no-op (no throw)

## How the loader works

The static JS files are written as **classic browser scripts** (IIFEs and
top-level function declarations), not ES modules. To execute them faithfully
inside jsdom, the test helper [`tests/js/helpers/loadScript.mjs`](../../tests/js/helpers/loadScript.mjs)
reads the file and injects it as a `<script>` element:

```js
const script = document.createElement("script");
script.textContent = code;
document.head.appendChild(script);
```

This mirrors the real browser execution model — function declarations become
window properties, IIFEs run, and event listeners attach correctly. After
loading the script, tests dispatch a fresh `DOMContentLoaded` event so any
listeners registered by the script (which assume the document is still
loading) fire as expected.

## Adding a new test

1. Add or update the file in `coyote/static/js/`.
2. Create `tests/js/<name>.test.mjs`.
3. Use `loadScript("<name>.js")` and exercise the resulting globals or DOM.
4. Run `npm test` and ensure it passes.

## CI integration

Add `npm test` to the JS quality job alongside `npm run e2e` so unit tests run
on every push. Vitest exits non-zero on failure.
