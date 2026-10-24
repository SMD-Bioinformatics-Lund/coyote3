import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { expect, it } from "vitest"
import { DiagnosisNavigation } from "./DiagnosisNavigation"

it("marks the current tab and navigates between diagnosis pages", () => {
  render(
    <MemoryRouter initialEntries={["/admin/diagnoses"]}>
      <Routes>
        <Route path="/admin/diagnoses" element={<DiagnosisNavigation active="definitions" />} />
        <Route path="/admin/assay-diagnoses" element={<DiagnosisNavigation active="associations" />} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByRole("tablist", { name: "Diagnosis administration" })).toBeVisible()
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "true")
  fireEvent.click(screen.getByRole("tab", { name: "Assay associations" }))
  expect(screen.getByRole("tab", { name: "Assay associations" })).toHaveAttribute("aria-selected", "true")
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "false")
  fireEvent.click(screen.getByRole("tab", { name: "Definitions" }))
  expect(screen.getByRole("tab", { name: "Definitions" })).toHaveAttribute("aria-selected", "true")
})
