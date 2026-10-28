import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { DatabaseBrand } from "./DatabaseBrand"

it("uses the logo without repeating its database name", () => {
  render(<DatabaseBrand source="cosmic" label="COSMIC" />)
  expect(screen.getByRole("img", { name: "COSMIC logo" })).toBeVisible()
  expect(screen.queryByText("COSMIC")).not.toBeInTheDocument()
})

it("preserves product qualifiers beside a logo", () => {
  render(<DatabaseBrand source="oncokb_public" label="OncoKB Public" />)
  expect(screen.getByRole("img", { name: "OncoKB logo" })).toBeVisible()
  expect(screen.getByText("Public")).toBeVisible()
  expect(screen.queryByText("OncoKB Public")).not.toBeInTheDocument()
})

it("uses text when a source has no logo", () => {
  render(<DatabaseBrand source="iarc_tp53" label="IARC TP53" />)
  expect(screen.getByText("IARC TP53")).toBeVisible()
  expect(screen.queryByRole("img")).not.toBeInTheDocument()
})

it("falls back after an image fails and loads the next source independently", () => {
  const view = render(<DatabaseBrand source="cosmic" label="COSMIC" />)
  fireEvent.error(screen.getByRole("img"))
  expect(screen.getByText("COSMIC")).toBeVisible()
  expect(screen.queryByRole("img")).not.toBeInTheDocument()
  view.rerender(<DatabaseBrand source="civic" label="CIViC" />)
  expect(screen.getByRole("img", { name: "CIViC logo" })).toBeVisible()
  expect(screen.queryByText("CIViC")).not.toBeInTheDocument()
})
