import { readFileSync, readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"

const root = new URL("../src", import.meta.url).pathname
const pageFrame = "components/layout/PageFrame.tsx"
const sourceExtensions = new Set([".css", ".ts", ".tsx"])
const failures = []

function filesUnder(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    return statSync(path).isDirectory() ? filesUnder(path) : [path]
  })
}

function report(file, line, rule) {
  failures.push(`${relative(root, file)}:${line}: ${rule}`)
}

for (const file of filesUnder(root)) {
  const extension = file.slice(file.lastIndexOf("."))
  if (!sourceExtensions.has(extension)) continue

  const relativePath = relative(root, file)
  const lines = readFileSync(file, "utf8").split("\n")
  lines.forEach((line, index) => {
    const lineNumber = index + 1
    if (/\btransition-all\b/.test(line)) report(file, lineNumber, "use a scoped transition utility")
    if (/\bfont-(?:black|extrabold)\b/.test(line)) report(file, lineNumber, "use a semantic typography role or a restrained weight")
    if (/\btext-\[/.test(line)) report(file, lineNumber, "use a semantic typography or color utility")
    if (
      relativePath !== pageFrame
      && relativePath !== "styles/tailwind-theme.css"
      && !relativePath.endsWith(".test.tsx")
      && !relativePath.endsWith(".test.ts")
      && /\bresponsive-page-padding\b/.test(line)
    ) {
      report(file, lineNumber, "PageFrame is the sole owner of route gutters")
    }
  })

  if (relativePath.startsWith("pages/")) {
    lines.forEach((line, index) => {
      if (/\b(?:bg|text|border|ring|from|via|to)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-|\/|\b)/.test(line)) {
        report(file, index + 1, "use a semantic or domain theme token instead of a raw palette color")
      }
    })
  }
}

if (failures.length > 0) {
  console.error("Design-system contract violations:\n")
  console.error(failures.join("\n"))
  process.exit(1)
}

console.log("Design-system contract passed.")
