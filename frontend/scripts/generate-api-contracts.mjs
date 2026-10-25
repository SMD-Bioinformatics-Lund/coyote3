/** Generate/check TypeScript contracts from a running API or the canonical source app. */
import { spawnSync } from "node:child_process"
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { createClient, toCase } from "@hey-api/openapi-ts"

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const root = path.dirname(frontend)
const output = path.join(frontend, "src/lib/generated")
const check = process.argv.includes("--check")
const urlIndex = process.argv.indexOf("--url")
const sourceUrl = urlIndex >= 0 ? process.argv[urlIndex + 1] : process.env.COYOTE3_OPENAPI_URL
if (urlIndex >= 0 && !sourceUrl) throw new Error("--url requires the server's complete OpenAPI URL")
const temporary = await mkdtemp(path.join(tmpdir(), "coyote3-openapi-"))
/** Sort object keys so a running server and a source export generate identical types. */
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === "object") return Object.fromEntries(
    Object.entries(value).sort(([a], [b]) => a.localeCompare(b, "en")).map(([key, item]) => [key, canonical(item)]),
  )
  return value
}
try {
  const input = path.join(temporary, "openapi.json")
  if (sourceUrl) {
    const url = new URL(sourceUrl)
    if (!new Set(["http:", "https:"]).has(url.protocol) || url.username || url.password) {
      throw new Error("Use an HTTP(S) schema URL without embedded credentials")
    }
    const response = await fetch(url, { signal: AbortSignal.timeout(30000), redirect: "error" })
    if (!response.ok) throw new Error(`OpenAPI request failed with HTTP ${response.status}`)
    const schema = await response.json()
    if (!schema.openapi || !schema.paths || !schema.components) throw new Error("Server did not return an OpenAPI contract")
    delete schema.servers
    schema.info = { title: "Coyote3 API", version: "1" }
    await writeFile(input, JSON.stringify(schema))
  } else {
    const python = process.env.PYTHON_BIN || path.join(root, ".venv/bin/python")
    const result = spawnSync(python, ["scripts/contracts/export_openapi.py", "--output", input], {
      cwd: root, stdio: "inherit", env: process.env,
    })
    if (result.error) throw result.error
    if (result.status !== 0) throw new Error("Canonical API schema export failed")
  }
  await writeFile(input, JSON.stringify(canonical(JSON.parse(await readFile(input, "utf8")))))
  const generated = check ? path.join(temporary, "generated") : output
  await createClient({ input, output: generated, plugins: [{
    name: "@hey-api/typescript",
    requests: { case: "preserve", name: "Request_{{name}}" },
    responses: { case: "preserve", name: "Responses_{{name}}", response: "Response_{{name}}" },
  }] })
  const schema = JSON.parse(await readFile(input, "utf8"))
  const types = await readFile(path.join(generated, "types.gen.ts"), "utf8")
  const operations = []
  for (const [route, methods] of Object.entries(schema.paths).sort()) {
    for (const [method, operation] of Object.entries(methods).sort()) {
      if (!new Set(["get", "post", "put", "patch", "delete", "head", "options"]).has(method)) continue
      const bodyTypes = Object.keys(operation.requestBody?.content ?? {})
      if (bodyTypes.length && !bodyTypes.includes("application/json")) continue
      const success = Object.entries(operation.responses ?? {}).filter(([status]) => /^2/.test(status))
      if (!success.some(([, response]) => response.content?.["application/json"])) continue
      const name = toCase(operation.operationId, "camelCase")
      if (!types.includes(`export type Request_${name} =`)) {
        throw new Error(`Missing generated operation types: ${method} ${route}`)
      }
      const response = types.includes(`export type Response_${name} =`) ? `T.Response_${name}` : "unknown"
      operations.push(`  ${JSON.stringify(`${method.toUpperCase()} ${route.replace(/^\/api\/v1/, "")}`)}: { request: T.Request_${name}; response: ${response} }`)
    }
  }
  await writeFile(path.join(generated, "operations.gen.ts"),
    "// Generated from FastAPI OpenAPI. Do not edit.\nimport type * as T from './types.gen'\n\nexport type ApiOperations = {\n" + operations.join("\n") + "\n}\n")
  if (check) {
    const expected = (await readdir(generated)).sort()
    const existing = (await readdir(output)).sort()
    if (JSON.stringify(expected) !== JSON.stringify(existing)) throw new Error("Generated API contract file list is stale")
    for (const name of expected) {
      if (await readFile(path.join(generated, name), "utf8") !== await readFile(path.join(output, name), "utf8")) {
        throw new Error(`Stale API contract: ${name}. Run npm run api:generate against the matching API revision.`)
      }
    }
    process.stdout.write("Generated API contracts match the authoritative FastAPI schema.\n")
  }
} finally {
  await rm(temporary, { recursive: true, force: true })
}
