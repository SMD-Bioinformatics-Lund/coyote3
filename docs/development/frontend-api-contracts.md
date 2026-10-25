# Frontend API contracts

FastAPI's OpenAPI document is the authority for HTTP paths, parameters, bodies and
responses. `@hey-api/openapi-ts` generates TypeScript types into
`frontend/src/lib/generated/`; these files are derived and must not be edited manually.
The generator is pinned and supports the repository's TypeScript 6 compiler.
It generates types for the existing HTTP wrapper; it does not create a second
runtime client or replace the independent Python client package.

## Check a running server

To generate from a running deployment, include its application prefix:

```bash
npm --prefix frontend run api:generate -- \
  --url https://COYOTE_HOST/COYOTE_PREFIX/api/v1/openapi.json
npm --prefix frontend run api:check -- \
  --url https://COYOTE_HOST/COYOTE_PREFIX/api/v1/openapi.json
```

`COYOTE3_OPENAPI_URL` supplies the same URL. TLS verification remains enabled;
configure the institution's trusted CA through Node's supported CA settings when
needed. A remote fetch failure is an error, not a fallback to another schema.

## Check a backend revision

Without a URL, the generator imports the FastAPI application and calls
its OpenAPI generator without starting database, Redis or worker lifecycles. The
JSON file is temporary and removed afterwards; there is no separately maintained
local schema. Select the matching center vocabulary when exporting center-specific
contracts. Host URLs, deployment descriptions and application release labels are
excluded from generated type comparisons; HTTP contracts remain intact.

```bash
npm --prefix frontend run api:generate
npm --prefix frontend run build:verified
```

`build:verified` checks generated types against the selected source/server and then
builds the UI. CI runs it on every non-draft change, including backend-only changes.
Plain `build` compiles the checked-in generated contracts and remains available for
the independent Node-only frontend container build. Production builds do not need
access to a live clinical deployment. A running server check is useful for verifying
the deployed contract; it cannot establish what an unreleased backend revision exposes.

## Use generated types

For JSON operations, `api.contract("GET /samples", { query: { live_page: 1 } })` checks operation names,
path/query fields and bodies and uses the existing authentication, CSRF, cancellation
and error handling. Existing URL-based calls remain supported. Sample lists, navigation
counts and report previews/trials consume generated response types. UI display models
remain separate from transport contracts. Compile-time assertions reject invented
operations and invalid parameter/body types.
Multipart uploads and binary/text downloads retain their explicit existing transports;
they are excluded from the JSON-operation helper, while their documented types are
still generated.

## Limits

Generation does not validate runtime JSON or replace permission checks. Fields
declared as unstructured dictionaries by the backend remain `unknown` until narrowed;
endpoints without a documented response schema cannot acquire precise types from
code generation alone. Preserve those distinctions when tightening contracts.
