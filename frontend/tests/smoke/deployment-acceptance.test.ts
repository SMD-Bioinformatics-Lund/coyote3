// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { FullConfig, FullResult, Suite, TestCase, TestResult } from "@playwright/test/reporter"
import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it, vi } from "vitest"
import { deploymentSettings, reportPackageVersion, validateReleaseArguments } from "../e2e-real/support/deployment-settings"
import RequireCompleteAcceptance from "../e2e-real/support/require-complete-acceptance"

import { stackState, validateState, type StackState } from "../e2e-real/support/disposable-stack"

const disposable = (): StackState => ({
  format: 1, project: "coyote4-demo-1234abcd", pid: process.pid, created: Date.now() / 1000,
  baseURL: "http://127.0.0.1:41833/",
  databases: { COYOTE4_DB: "coyote4_demo", IDENTITY_DB: "coyote4_demo_identity",
    KNOWLEDGEBASE_DB: "coyote4_demo_knowledgebase", BAM_DB: "coyote4_demo_bam" },
  containers: { frontend: "a".repeat(64), "demo-mongo": "b".repeat(64), worker: "c".repeat(64) },
  username: "synthetic", password: "synthetic", superuser: "synthetic-admin", superuserPassword: "synthetic",
  reviewPassword: "synthetic", dnaSample: "DEMO_STARTER_DNA", rnaSample: "DEMO_STARTER_RNA",
})

describe("disposable browser target safety", () => {
  it("accepts the generated local synthetic target", () => expect(() => validateState(disposable())).not.toThrow())
  it.each(["https://production.example.test/", "http://10.1.1.1:8000/", "http://localhost:8000/", "http://127.0.0.1:8000/prod/", "http://user:secret@127.0.0.1:8000/"])(
    "rejects an arbitrary or production browser target", baseURL => {
      expect(() => validateState({ ...disposable(), baseURL })).toThrow("local disposable")
    },
  )
  it.each(["COYOTE4_DB", "IDENTITY_DB", "KNOWLEDGEBASE_DB", "BAM_DB"])(
    "rejects an ordinary %s database even on localhost", key => {
      const state = disposable()
      state.databases[key] = "coyote4_production"
      expect(() => validateState(state)).toThrow("never use production")
    },
  )
  it("rejects a stale stack proof", () => {
    expect(() => validateState({ ...disposable(), created: 1 })).toThrow("expired")
  })
  it("rejects malformed container identities before invoking Docker", () => {
    expect(() => validateState({ ...disposable(), containers: { worker: "existing-worker" } })).toThrow("identities")
  })
  it("rejects an existing deployment URL even when a proof is supplied", () => {
    expect(() => stackState({ COYOTE4_E2E_BASE_URL: "http://127.0.0.1:8000/", COYOTE4_E2E_STATE: "unused" }))
      .toThrow("Existing deployment targets are forbidden")
  })
  it("rejects direct invocation without the disposable runner", () => {
    expect(() => deploymentSettings({})).toThrow("install.sh test-browser")
  })
})

describe("report renderer identity", () => {
  it.each([
    'reporting = ["Jinja2==3.1.6", "smd-reports==1.2.3"]',
    "reporting = [\n  'smd-reports==1.2.3', # renderer\n]",
  ])("reads the reporting extra regardless of TOML layout", reporting => {
    expect(reportPackageVersion(`[project.optional-dependencies]\n${reporting}`)).toBe("1.2.3")
  })

  it("loads the renderer identity from the release checkout", () => {
    const manifest = readFileSync(path.resolve(
      path.dirname(fileURLToPath(import.meta.url)), "../../../core/pyproject.toml",
    ), "utf8")
    expect(reportPackageVersion(manifest)).toMatch(/^\d+\.\d+\.\d+/)
  })

  it("does not treat comments or unrelated extras as the renderer selection", () => {
    expect(reportPackageVersion(`[project.optional-dependencies]
# smd-reports==9.0.0
test = ["smd-reports==8.0.0"]
reporting = ["smd-reports==1.2.3"]`)).toBe("1.2.3")
  })

  it.each(['[]', '["smd-reports>=1.0"]', '["smd-reports==1.*"]', '["smd-reports==1.0", "smd-reports==2.0"]'])(
    "rejects missing, unpinned or duplicate renderer identities",
    dependencies => expect(() => reportPackageVersion(
      `[project.optional-dependencies]\nreporting = ${dependencies}`,
    )).toThrow("one exact smd-reports dependency"),
  )

  it("rejects malformed TOML", () => {
    expect(() => reportPackageVersion('[project\n')).toThrow("valid TOML")
  })
})

describe("release command completeness", () => {
  it("allows the full suite with explicit execution and output controls", () => {
    expect(() => validateReleaseArguments([
      "test", "--config=playwright.real.config.ts", "--workers", "2", "--retries=1",
      "--headed", "--output", "test-results", "--trace=retain-on-failure", "-x",
    ])).not.toThrow()
  })

  it.each([
    ["--grep=reports"], ["-g", "reports"], ["--grep-invert", "RNA"], ["-G", "RNA"],
    ["authenticated-routes.spec.ts"], ["--", "public-routes"], ["--project=chromium-real"],
    ["--shard=1/2"], ["--test-list", "selected.txt"], ["--test-list-invert", "excluded.txt"],
    ["--last-failed"], ["--only-changed"], ["--list"], ["--reporter=line"], ["--ui"],
    ["--pass-with-no-tests"], ["--ignore-snapshots"], ["--update-snapshots"],
    ["--no-deps"], ["--workers"], ["--workers="], ["--headed=false"],
  ])("rejects selective or guard-changing CLI arguments: %s", (...options) => {
    expect(() => validateReleaseArguments(["test", ...options])).toThrow("complete suite")
  })

  it("requires a real test execution command", () => {
    expect(() => validateReleaseArguments(["show-report"])).toThrow("test command")
  })
})

describe("complete release execution", () => {
  const scenario = {
    id: "report-preview", titlePath: () => ["synthetic", "report preview"], expectedStatus: "passed",
  } as TestCase
  const passed = { status: "passed" } as FullResult
  const suite = { allTests: () => [scenario] } as Suite

  it("preserves the runner result when every collected scenario passed", async () => {
    const reporter = new RequireCompleteAcceptance()
    reporter.onBegin({} as FullConfig, suite)
    reporter.onTestEnd(scenario, { status: "passed" } as TestResult)
    expect(await reporter.onEnd(passed)).toBeUndefined()
    expect(await reporter.onEnd({ status: "failed" } as FullResult)).toBeUndefined()
  })

  it("fails a skipped scenario even when Playwright otherwise reports success", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    const reporter = new RequireCompleteAcceptance()
    reporter.onBegin({} as FullConfig, suite)
    reporter.onTestEnd(scenario, { status: "skipped" } as TestResult)
    expect(await reporter.onEnd(passed)).toEqual({ status: "failed" })
  })

  it("does not accept an empty release run", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    expect(await new RequireCompleteAcceptance().onEnd(passed)).toEqual({ status: "failed" })
  })

  it("rejects collected scenarios that never receive a completion", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    const reporter = new RequireCompleteAcceptance()
    reporter.onBegin({} as FullConfig, {
      allTests: () => [scenario, { ...scenario, id: "unexecuted-scenario" }],
    } as Suite)
    reporter.onTestEnd(scenario, { status: "passed" } as TestResult)
    expect(await reporter.onEnd(passed)).toEqual({ status: "failed" })
  })

  it("rejects a failed attempt even when its retry passes", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    const reporter = new RequireCompleteAcceptance()
    reporter.onBegin({} as FullConfig, suite)
    reporter.onTestEnd(scenario, { status: "failed" } as TestResult)
    reporter.onTestEnd(scenario, { status: "passed" } as TestResult)
    expect(await reporter.onEnd(passed)).toEqual({ status: "failed" })
  })

  it("rejects expected failures rather than treating them as acceptance", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    const reporter = new RequireCompleteAcceptance()
    reporter.onBegin({} as FullConfig, suite)
    reporter.onTestEnd({ ...scenario, expectedStatus: "failed" } as TestCase, { status: "failed" } as TestResult)
    expect(await reporter.onEnd(passed)).toEqual({ status: "failed" })
  })

  it.each(["interrupted", "failed", "timedout"] as const)("retains an existing %s result", async status => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    expect(await new RequireCompleteAcceptance().onEnd({ status } as FullResult))
      .toEqual({ status })
  })
})
