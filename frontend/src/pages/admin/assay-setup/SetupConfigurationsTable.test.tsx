import { fireEvent, render, screen, within } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { SetupConfigurationsTable } from "./SetupConfigurationsTable"

it("limits scope rows to ten and offers edit or create for the selected scope", () => {
  const edit = vi.fn(), create = vi.fn()
  render(<SetupConfigurationsTable scopes={["base", "breast", "lung"]} environments={["production", "testing", "development", "validation"]} records={[{ diagnosis_id: "base", environment: "production", display_name: "Reviewed production config" }]} readonly={false} pending={false} formAvailable onEdit={edit} onCreate={create} onRemove={() => {}} />)
  const table = screen.getByRole("table")
  expect(within(table).getAllByRole("row")).toHaveLength(11)
  expect(screen.getByText("Reviewed production config")).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: "Edit base production" }))
  expect(edit).toHaveBeenCalledWith(0)
  fireEvent.click(screen.getByRole("button", { name: "Next configurations" }))
  expect(within(table).getAllByRole("row")).toHaveLength(3)
  fireEvent.click(screen.getByRole("button", { name: "Add configuration lung validation" }))
  expect(create).toHaveBeenCalledWith("lung", "validation")
  expect(screen.getByRole("button", { name: "Next configurations" })).toBeDisabled()
})

it("requires only Base production and labels other missing configurations optional", () => {
  render(<SetupConfigurationsTable scopes={["base", "lung"]} environments={["development", "production"]} records={[]} readonly={false} pending={false} formAvailable onEdit={() => {}} onCreate={() => {}} onRemove={() => {}} />)
  expect(screen.getAllByText("Missing required")).toHaveLength(1)
  expect(screen.getAllByText("Optional")).toHaveLength(3)
  expect(within(screen.getAllByRole("row")[1]).getByRole("button", { name: "Add configuration base production" })).toBeEnabled()
})
