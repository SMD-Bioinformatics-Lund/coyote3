import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { render } from "@testing-library/react"

export function renderWithRouter(ui: ReactElement, initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      {ui}
    </MemoryRouter>,
  )
}
