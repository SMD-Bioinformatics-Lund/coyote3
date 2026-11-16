// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { FullConfig, FullResult, Suite, TestCase, TestResult } from "@playwright/test/reporter"
import { describe, expect, it, vi } from "vitest"
import { deploymentSettings, reportPackageVersion, validateReleaseArguments } from "../e2e-real/support/deployment-settings"
import RequireCompleteAcceptance from "../e2e-real/support/require-complete-acceptance"

const releaseEnvironment = {
  COYOTE4_E2E_RELEASE: "1",
  COYOTE4_E2E_BASE_URL: "https://validation.example.test/coyote4",
  COYOTE4_E2E_USERNAME: "synthetic-reviewer",
  COYOTE4_E2E_PASSWORD: "synthetic-test-password",
  COYOTE4_E2E_DNA_SAMPLE: "SYNTHETIC_DNA",
  COYOTE4_E2E_RNA_SAMPLE: "SYNTHETIC_RNA",
}

describe("deployment acceptance prerequisites", () => {
  it("preserves the deployment prefix and verifies TLS by default", () => {
    expect(deploymentSettings(releaseEnvironment)).toEqual({
      baseURL: "https://validation.example.test/coyote4/",
      release: true,
      ignoreHTTPSErrors: false,
    })
  })

  it.each(Object.keys(releaseEnvironment).filter(name => name !== "COYOTE4_E2E_RELEASE"))(
    "rejects a release run missing %s before starting the browser",
    name => {
      expect(() => deploymentSettings({ ...releaseEnvironment, [name]: " " })).toThrow(name)
    },
  )

  it("allows a public smoke run without credentials or clinical samples", () => {
    expect(deploymentSettings({ COYOTE4_E2E_BASE_URL: "http://localhost/coyote4_dev" })).toEqual({
      baseURL: "http://localhost/coyote4_dev/", release: false, ignoreHTTPSErrors: false,
    })
  })

  it.each(["https://localhost/", "https://127.0.0.1/", "https://[::1]/"])(
    "allows an explicit self-signed development certificate only at %s",
    baseURL => expect(deploymentSettings({
      COYOTE4_E2E_BASE_URL: baseURL, COYOTE4_E2E_ALLOW_SELF_SIGNED: "1",
    }).ignoreHTTPSErrors).toBe(true),
  )

  it.each(["http://localhost/", "https://validation.example.test/"])(
    "rejects certificate bypass for %s",
    baseURL => expect(() => deploymentSettings({
      COYOTE4_E2E_BASE_URL: baseURL, COYOTE4_E2E_ALLOW_SELF_SIGNED: "1",
    })).toThrow("local HTTPS development"),
  )

  it("never permits a release to bypass certificate validation", () => {
    expect(() => deploymentSettings({ ...releaseEnvironment,
      COYOTE4_E2E_BASE_URL: "https://localhost/", COYOTE4_E2E_ALLOW_SELF_SIGNED: "1",
    })).toThrow("certificate verification")
  })

  it("requires HTTPS for release acceptance", () => {
    expect(() => deploymentSettings({ ...releaseEnvironment,
      COYOTE4_E2E_BASE_URL: "http://validation.example.test/",
    })).toThrow("HTTPS")
  })

  it.each(["not-a-url", "file:///tmp/test", "https://name:password@example.test/", "https://example.test/?token=secret", "https://example.test/#fragment"])(
    "rejects invalid or credential-bearing base URL without echoing its contents",
    baseURL => {
      try {
        deploymentSettings({ COYOTE4_E2E_BASE_URL: baseURL })
        throw new Error("Expected invalid URL to be rejected")
      } catch (error) {
        expect(String(error)).toContain("COYOTE4_E2E_BASE_URL")
        expect(String(error)).not.toContain(baseURL)
      }
    },
  )

  it.each(["COYOTE4_E2E_RELEASE", "COYOTE4_E2E_ALLOW_SELF_SIGNED"])(
    "rejects an ambiguous %s switch",
    name => expect(() => deploymentSettings({ ...releaseEnvironment, [name]: "true" })).toThrow("0 or 1"),
  )
})

describe("report renderer identity", () => {
  it("takes the exact version from dependency metadata", () => {
    expect(reportPackageVersion('[project]\ndependencies = [\n  "smd-reports==1.2.3",\n]\n')).toBe("1.2.3")
  })

  it.each(["", '"smd-reports>=1.0"', '"smd-reports==1.0"\n"smd-reports==2.0"'])(
    "rejects missing, unpinned or duplicate renderer identities",
    manifest => expect(() => reportPackageVersion(manifest)).toThrow("one exact smd-reports dependency"),
  )
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
