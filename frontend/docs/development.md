# Develop and verify the frontend

Run from the frontend directory:

```bash
npm run lint
npm run test:unit
npm run test:smoke
npm run test:coverage
npm run build:verified
npm run test:e2e
```

Lint includes the design-system checks. Unit/component tests use Vitest and
Testing Library. Browser tests use Playwright; tests targeting a running
deployment require their documented synthetic environment. Do not run them
against a clinical deployment without explicit authorization.

`build:verified` checks generated HTTP types before the production build.
Regenerate types with `npm run api:generate` when an intentional API contract
change requires it. Review the generated change alongside the server contract;
do not manually patch generated types.

Production output is written to `dist/`. `npm run preview` serves a local build
for inspection. Builds include `LICENSE.txt`, `COPYRIGHT.txt` and `NOTICE.txt`
from this project's root; retain these files when distributing the frontend.
Preview does not provision backend services. Full release and proxy configuration
remain application deployment responsibilities.

Most module, component and page tests are colocated under `src`. The separately
selectable `tests/smoke` suite exercises the shared confirmation dialog, including
keyboard handling, focus and pending actions. It runs in jsdom without a backend
or external services, and is also included in the full Vitest suite.

`test:coverage` measures all configured frontend source files and writes its own
reports to `coverage/`. Existing floors remain 75% statements, 60% branches, 65%
functions and 77% lines. Smoke checks do not enforce the full-suite coverage floor.
Playwright browser and configured-deployment suites remain separate checks.
