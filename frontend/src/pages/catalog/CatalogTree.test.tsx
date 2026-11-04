import { useState } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { CatalogTree } from "./CatalogTree"
import { effectiveCatalogEntry } from "../admin/catalog-hierarchy"
import type { Modality } from "../admin/catalog-types"

const section: Modality = { label: "DNA", categories: {
  panels: { label: "Panels", node_kind: "folder", tat: "10 days" },
  solid: { label: "Solid", node_kind: "folder", parent_key: "panels", analysis: ["SNV"] },
  breast: { label: "Breast", parent_key: "solid" },
  colon: { label: "Colon", parent_key: "solid", analysis: ["CNV"], tat: "", clear_fields: ["tat"] },
} }

it("opens a nested branch and keeps analyses out of the navigation", () => {
  function Navigation() {
    const [selected, setSelected] = useState<string>()
    return <CatalogTree categories={section.categories} selected={selected} onSelect={setSelected} />
  }
  render(<Navigation />)
  expect(screen.queryByRole("button", { name: "Breast" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Expand Panels" }))
  expect(screen.getByRole("button", { name: "Solid" })).toBeVisible()
  expect(screen.getByRole("button", { name: "Panels" })).not.toHaveAttribute("aria-current")
  fireEvent.click(screen.getByRole("button", { name: "Collapse Panels" }))
  expect(screen.queryByRole("button", { name: "Solid" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Panels" }))
  fireEvent.click(screen.getByRole("button", { name: "Solid" }))
  fireEvent.click(screen.getByRole("button", { name: "Breast" }))
  expect(screen.getByRole("button", { name: "Breast" })).toHaveAttribute("aria-current", "page")
  expect(screen.getByRole("button", { name: "Colon" })).toBeVisible()
  expect(screen.queryByRole("tab")).not.toBeInTheDocument()
})

it("resolves immediate-parent choices without mutating the draft", () => {
  const before = JSON.stringify(section)
  expect(effectiveCatalogEntry(section, "breast")).toMatchObject({ label: "Breast", analysis: ["SNV"], tat: "10 days" })
  expect(effectiveCatalogEntry(section, "colon")).toMatchObject({ analysis: ["CNV"], tat: "" })
  expect(JSON.stringify(section)).toBe(before)
})

it("retains a collapsed selected branch across edits and opens a newly selected path", () => {
  const categories = {
    dna: { label: "DNA" },
    panels: { label: "Panels", parent_key: "dna" },
    mpn: { label: "MPN", parent_key: "panels" },
  }
  const onSelect = vi.fn()
  const { rerender } = render(<CatalogTree categories={categories} selected="panels" onSelect={onSelect} />)
  fireEvent.click(screen.getByRole("button", { name: "Collapse DNA" }))
  rerender(<CatalogTree categories={structuredClone(categories)} selected="panels" onSelect={onSelect} />)
  expect(screen.getByRole("button", { name: "Expand DNA" })).toHaveAttribute("aria-expanded", "false")
  expect(screen.queryByRole("button", { name: "Panels" })).not.toBeInTheDocument()
  expect(onSelect).not.toHaveBeenCalled()
  rerender(<CatalogTree categories={categories} selected="mpn" onSelect={onSelect} />)
  expect(screen.getByRole("button", { name: "MPN" })).toHaveAttribute("aria-current", "page")
})
