import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { expect, it } from "vitest"
import { SubpanelNavigation } from "./SubpanelNavigation"

it("marks the current tab and navigates between subpanel pages", () => {
  render(
    <MemoryRouter initialEntries={["/admin/subpanels"]}>
      <Routes>
        <Route path="/admin/subpanels" element={<SubpanelNavigation active="definitions" />} />
        <Route path="/admin/assay-subpanels" element={<SubpanelNavigation active="associations" />} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByRole("tablist", { name: "Subpanel administration" })).toBeVisible()
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "true")
  fireEvent.click(screen.getByRole("tab", { name: "Assay associations" }))
  expect(screen.getByRole("tab", { name: "Assay associations" })).toHaveAttribute("aria-selected", "true")
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "false")
  fireEvent.click(screen.getByRole("tab", { name: "Definitions" }))
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "true")
})
