import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { expect, it, vi } from "vitest"
import { ExpandableText } from "./ExpandableText"

it("reports clipboard failure instead of claiming a successful copy", async () => {
  const user = userEvent.setup()
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("Denied"))
  render(<ExpandableText text="synthetic text" />)
  await user.click(screen.getByTitle("Copy to clipboard"))
  expect(await screen.findByRole("alert")).toHaveTextContent(/copy/i)
})

it("expands and copies without submitting an enclosing form", async () => {
  const user = userEvent.setup()
  const submit = vi.fn(event => event.preventDefault())
  render(<form onSubmit={submit}><ExpandableText text="Long synthetic text" maxLength={4} /></form>)
  await user.click(screen.getByRole("button", { name: "Show full value" }))
  await user.click(screen.getByTitle("Copy to clipboard"))
  expect(submit).not.toHaveBeenCalled()
})
