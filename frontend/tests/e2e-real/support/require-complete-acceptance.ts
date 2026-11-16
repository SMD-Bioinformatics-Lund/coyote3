// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { FullConfig, FullResult, Reporter, Suite, TestCase, TestResult } from "@playwright/test/reporter"

/** Prevent a release run with unexecuted scenarios from being recorded as passing. */
export default class RequireCompleteAcceptance implements Reporter {
  private expected = new Map<string, string>()
  private completed = new Set<string>()
  private unsuccessful = new Set<string>()

  onBegin(_config: FullConfig, suite: Suite) {
    this.expected = new Map(suite.allTests().map(test => [test.id, test.titlePath().join(" > ")]))
  }

  onTestEnd(test: TestCase, result: TestResult) {
    this.completed.add(test.id)
    if (result.status !== "passed" || test.expectedStatus !== "passed") {
      this.unsuccessful.add(test.titlePath().join(" > "))
    }
  }

  async onEnd(result: FullResult): Promise<{ status: FullResult["status"] } | undefined> {
    const missing = [...this.expected].filter(([id]) => !this.completed.has(id))
    if (this.expected.size > 0 && missing.length === 0 && this.unsuccessful.size === 0) return undefined
    console.error("Release acceptance is incomplete: every scenario must execute and pass without retries.")
    for (const [, title] of missing) console.error(`Not completed: ${title}`)
    for (const title of this.unsuccessful) console.error(`Did not pass on every attempt: ${title}`)
    return { status: result.status === "passed" ? "failed" : result.status }
  }
}
