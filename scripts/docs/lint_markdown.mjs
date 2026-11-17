// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/** Lint repository Markdown with the shared rules and explicit source boundaries. */
import { readdir, readFile, stat } from "node:fs/promises"
import { existsSync } from "node:fs"
import { execFileSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { lint } from "markdownlint/promise"

const repository = fileURLToPath(new URL("../../", import.meta.url))
const defaultInputs = [
  "README.md", "docs", ".github",
  "core/README.md", "core/docs",
  "api/README.md", "api/docs",
  "adapters/mongo/README.md", "adapters/mongo/docs",
  "services/atlas/README.md", "services/atlas/docs",
  "services/demo/README.md", "services/demo/docs",
  "frontend/README.md", "frontend/docs",
].map((name) => path.join(repository, name))
const readmes = execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "-z"], { cwd: repository, encoding: "utf8" })
  .split("\0")
  .filter((name) => path.basename(name) === "README.md")
  .map((name) => path.join(repository, name))
  .filter(existsSync)
defaultInputs.push(...readmes)
const excludedFiles = new Set([
  ".github/pull_request_template.md",
  "docs/reference/mongodb-collections.md",
])

/** Collect Markdown recursively, preserving the repository's generated/template exclusions. */
export async function markdownFiles(inputs = defaultInputs) {
  const files = new Set()
  async function visit(candidate) {
    const relative = path.relative(repository, candidate).split(path.sep).join("/")
    if (excludedFiles.has(relative) || relative.startsWith(".github/ISSUE_TEMPLATE/")) return
    const info = await stat(candidate)
    if (info.isDirectory()) {
      for (const entry of await readdir(candidate, { withFileTypes: true })) {
        if (entry.isDirectory() || entry.isFile()) await visit(path.join(candidate, entry.name))
      }
    } else if (info.isFile() && path.extname(candidate).toLowerCase() === ".md") {
      files.add(candidate)
    }
  }
  for (const input of inputs) await visit(path.resolve(input))
  return [...files].sort()
}

/** Return markdownlint diagnostics for files using the repository rule configuration. */
export async function lintMarkdown(files) {
  const config = JSON.parse(await readFile(path.join(repository, ".markdownlint.json"), "utf8"))
  return lint({ files, config })
}

/** Print actionable diagnostics and return a failing status when lint finds a violation. */
export async function main(inputs = defaultInputs) {
  const files = await markdownFiles(inputs)
  if (!files.length) throw new Error("No Markdown files selected")
  const results = await lintMarkdown(files)
  let count = 0
  for (const [filename, errors] of Object.entries(results)) {
    for (const error of errors) {
      const detail = error.errorDetail ? ` (${error.errorDetail})` : ""
      console.error(`${path.relative(repository, filename)}:${error.lineNumber} ${error.ruleNames[0]} ${error.ruleDescription}${detail}`)
      count++
    }
  }
  console.log(`Markdown lint: ${files.length} files, ${count} errors`)
  return count ? 1 : 0
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await main(process.argv.length > 2 ? process.argv.slice(2) : defaultInputs)
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    process.exitCode = 1
  }
}
