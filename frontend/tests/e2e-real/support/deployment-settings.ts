// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { execFileSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { stackState } from "./disposable-stack"

/** Resolve the newly created local stack before any browser or HTTP request. */
export function deploymentSettings(environment: NodeJS.ProcessEnv) {
  const state = stackState(environment)
  return { baseURL: state.baseURL, release: true, ignoreHTTPSErrors: false }
}

/** Keep release acceptance complete; selection and reporter overrides cannot be used. */
export function validateReleaseArguments(arguments_: readonly string[]): void {
  const [command, ...options] = arguments_
  if (command !== "test") throw new Error("Release acceptance must use the Playwright test command.")
  const flags = new Set(["--headed", "--quiet", "--forbid-only", "--fail-on-flaky-tests", "-x"])
  const valuedOptions = new Set([
    "--config", "-c", "--workers", "-j", "--retries", "--repeat-each", "--timeout",
    "--global-timeout", "--max-failures", "--output", "--trace",
  ])
  for (let index = 0; index < options.length; index += 1) {
    const argument = options[index]
    const separator = argument.indexOf("=")
    const name = separator < 0 ? argument : argument.slice(0, separator)
    if (flags.has(name) && separator < 0) continue
    if (valuedOptions.has(name)) {
      const value = separator < 0 ? options[++index] : argument.slice(separator + 1)
      if (value && !value.startsWith("-")) continue
    }
    throw new Error("Release acceptance requires the complete suite and its configured reporters. " +
      "Test filters, project selection, shards, listing and unsupported CLI overrides are not allowed.")
  }
}

/** Read the renderer pin from the core's authoritative dependency declaration. */
export function reportPackageVersion(manifest: string): string {
  const python = process.env.PYTHON_BIN || path.resolve(
    path.dirname(fileURLToPath(import.meta.url)), "../../../../.venv/bin/python",
  )
  const readReportingDependencies = [
    "import json, sys, tomllib",
    "project = tomllib.loads(sys.stdin.read())['project']",
    "print(json.dumps(project.get('optional-dependencies', {}).get('reporting', [])))",
  ].join("\n")
  let dependencies: unknown
  try {
    dependencies = JSON.parse(execFileSync(python, ["-c", readReportingDependencies], {
      input: manifest, encoding: "utf8", stdio: ["pipe", "pipe", "pipe"], timeout: 10_000,
    }))
  } catch {
    throw new Error("Cannot read core/pyproject.toml. Use valid TOML and Python 3.12+ via the workspace .venv or PYTHON_BIN.")
  }
  if (!Array.isArray(dependencies) || dependencies.some(value => typeof value !== "string")) {
    throw new Error("Expected a reporting dependency array in core/pyproject.toml.")
  }
  const declarations = dependencies.filter(value => /^smd-reports\b/.test(value))
  const version = declarations[0]?.match(/^smd-reports==([^\s,;*]+)$/)?.[1]
  if (declarations.length !== 1 || !version) {
    throw new Error("Expected one exact smd-reports dependency in core/pyproject.toml's reporting extra.")
  }
  return version
}
