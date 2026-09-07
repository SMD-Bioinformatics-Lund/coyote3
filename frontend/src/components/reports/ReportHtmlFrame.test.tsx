import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ReportHtmlFrame } from "./ReportHtmlFrame"

describe("ReportHtmlFrame", () => {
  it("uses srcDoc, an accessible title, and a minimum initial height", () => {
    render(<ReportHtmlFrame title="Clinical report preview" html="<h1>Report</h1>" minHeight={480} />)
    const frame = screen.getByTitle("Clinical report preview")
    expect(frame).toHaveAttribute("srcdoc", "<h1>Report</h1>")
    expect(frame).toHaveStyle({ height: "480px" })
    expect(frame).toHaveAttribute("scrolling", "no")
  })

  it("expands to the rendered report document height", () => {
    render(<ReportHtmlFrame title="Report" html="<p>Long report</p>" minHeight={100} />)
    const frame = screen.getByTitle("Report") as HTMLIFrameElement
    Object.defineProperty(frame.contentDocument?.body, "scrollHeight", { configurable: true, value: 640 })
    fireEvent.load(frame)
    expect(frame).toHaveStyle({ height: "644px" })
  })
})
