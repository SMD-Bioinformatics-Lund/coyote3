import { fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"
import { AssayIgvFields } from "./AssayIgvFields"

describe("ASP IGV folder editor", () => {
  it("edits structured fields and previews the combined path", () => {
    function Editor() {
      const [value, setValue] = useState<{base_folder?: string; bam_subfolder?: string; design_bed?: string} | null>(null)
      return <AssayIgvFields value={value} onChange={setValue} />
    }
    render(<Editor />)
    fireEvent.change(screen.getByLabelText("Base folder"), { target: { value: "gmshem" } })
    fireEvent.change(screen.getByLabelText("BAM subfolder"), { target: { value: "bam" } })
    fireEvent.change(screen.getByLabelText("Design BED"), { target: { value: "BED/design.bed" } })
    expect(screen.getByText("gmshem/bam/case.bam")).toBeInTheDocument()
    expect(screen.getByText("gmshem/BED/design.bed")).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Base folder"), { target: { value: "../escape" } })
    expect(screen.getByLabelText("Base folder")).toHaveAttribute("aria-invalid", "true")
    expect(screen.queryByText("BAM path preview")).not.toBeInTheDocument()
  })

  it("disables editing in read-only mode", () => {
    render(<AssayIgvFields value={{base_folder: "gmshem"}} onChange={vi.fn()} disabled />)
    expect(screen.getByLabelText("Base folder")).toBeDisabled()
    expect(screen.getByLabelText("Design BED")).toBeDisabled()
  })
})
