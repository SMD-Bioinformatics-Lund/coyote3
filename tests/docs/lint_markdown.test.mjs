import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { mkdtemp, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"
import { micromark } from "micromark"
import { math, mathHtml } from "micromark-extension-math"
import { lintMarkdown, markdownFiles } from "../../scripts/docs/lint_markdown.mjs"

const runner = fileURLToPath(new URL("../../scripts/docs/lint_markdown.mjs", import.meta.url))

test("repository discovery includes source documentation and excludes templates and generated contracts", async () => {
  const files = await markdownFiles()
  const relative = files.map((file) => path.relative(process.cwd(), file).split(path.sep).join("/"))
  assert.ok(relative.includes("README.md"))
  assert.ok(relative.includes("docs/testing/demo-data-bundle.md"))
  assert.ok(!relative.some((file) => file.startsWith(".github/ISSUE_TEMPLATE/")))
  assert.ok(!relative.includes(".github/pull_request_template.md"))
  assert.ok(!relative.includes("docs/reference/mongodb-collections.md"))
})

test("lint reports all existing rule families while respecting code fences", async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "coyote-markdown-"))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const valid = path.join(directory, "valid.md")
  const invalid = path.join(directory, "invalid.md")
  await writeFile(valid, "# Synthetic example\n\nA paragraph.\n\n```text\nline\n\n\nline\n```\n")
  await writeFile(invalid, "# Synthetic example\nMissing heading spacing.\n- missing list spacing\n\n\nNo final newline")
  const results = await lintMarkdown([valid, invalid])
  assert.deepEqual(results[valid], [])
  const rules = new Set(results[invalid].map((error) => error.ruleNames[0]))
  for (const rule of ["MD012", "MD022", "MD032", "MD047"]) assert.ok(rules.has(rule), rule)
  const failure = spawnSync(process.execPath, [runner, invalid], { encoding: "utf8" })
  assert.equal(failure.status, 1)
  assert.match(failure.stderr, /MD022/)
  const success = spawnSync(process.execPath, [runner, valid], { encoding: "utf8" })
  assert.equal(success.status, 0)
  assert.match(success.stdout, /1 files, 0 errors/)
  const missing = spawnSync(process.execPath, [runner, path.join(directory, "missing.md")], { encoding: "utf8" })
  assert.equal(missing.status, 1)
})

test("the patched math renderer supports the tokenizer's inline and display interfaces", () => {
  for (const markdown of ["$x^2$", "$$\n\\frac{a}{b}\n$$"]) {
    const html = micromark(markdown, { extensions: [math()], htmlExtensions: [mathHtml()] })
    assert.match(html, /class="katex/)
    assert.match(html, /<math/)
  }
})
