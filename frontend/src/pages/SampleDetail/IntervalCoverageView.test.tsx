// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it, vi } from "vitest"
import { IntervalCoverageView } from "./IntervalCoverageView"

const download = vi.hoisted(() => vi.fn())
vi.mock("@/lib/browser-download", () => ({ downloadText: download }))

const intervals = [
  { id: "zero", chr: "7", start: 0, end: 9, avg_cov: 0, amplicon: "ZERO" },
  { id: "deep", chr: "X", start: 10, end: 10, avg_cov: 1200.5, amplicon: "DEEP" },
  { id: "unknown", chr: "7", start: 20, end: 29, avg_cov: null, amplicon: "UNKNOWN" },
]

it("shows stored intervals with inclusive lengths and distinct zero and missing depth", () => {
  render(<IntervalCoverageView intervals={intervals} cutoff={500} sampleId="SYNTHETIC" />)
  const zero = screen.getByRole("row", { name: /ZERO/ })
  expect(within(zero).getByText("7:0-9")).toBeVisible()
  expect(within(zero).getByText("10")).toBeVisible()
  expect(within(zero).getByText("0.0")).toBeVisible()
  const deep = screen.getByRole("row", { name: /DEEP/ })
  expect(within(deep).getByText("1")).toBeVisible()
  expect(within(deep).getByText("1200.5")).toBeVisible()
  expect(within(screen.getByRole("row", { name: /UNKNOWN/ })).getByText("—")).toBeVisible()
})

it("searches and exports the visible legacy intervals without changing depth values", async () => {
  const user = userEvent.setup()
  render(<IntervalCoverageView intervals={intervals} cutoff={500} sampleId="SYNTHETIC" />)
  await user.type(screen.getByRole("textbox", { name: "Search all columns..." }), "ZERO")
  expect(screen.getByRole("row", { name: /ZERO/ })).toBeVisible()
  expect(screen.queryByRole("row", { name: /DEEP/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: /Export to CSV/i }))
  expect(download).toHaveBeenCalled()
  const content = download.mock.calls.at(-1)?.find(value => typeof value === "string" && value.includes("ZERO"))
  expect(content).toContain("7:0-9")
  expect(content).toContain('"7:0-9","10","0","ZERO"')
  expect(content).not.toContain("UNKNOWN")
})

it("reports absent legacy measurements without implying zero coverage", () => {
  render(<IntervalCoverageView intervals={[]} cutoff={500} sampleId="EMPTY" />)
  expect(screen.getByText("No legacy coverage intervals are stored for this sample.")).toBeVisible()
  expect(screen.queryByText("0.0")).not.toBeInTheDocument()
})
