import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it, vi } from "vitest"
import { FileUpload } from "./file-upload"

it("allows selecting the same corrected file again after a failed import", async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  render(<FileUpload label="Configuration" onChange={onChange} />)
  const input = screen.getByLabelText("Configuration")
  const file = new File(['{}'], "synthetic.json", { type: "application/json" })
  await user.upload(input, file)
  await user.upload(input, file)
  expect(onChange).toHaveBeenCalledTimes(2)
})
