import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { EnvironmentBanner } from "./EnvironmentBanner"

describe("EnvironmentBanner", () => {
  it.each(["production", "prod", " Production "])("hides in %s", (environment) => {
    render(<EnvironmentBanner environment={environment} />)
    expect(screen.queryByRole("status")).not.toBeInTheDocument()
  })

  it.each(["development", "staging", "test", "validation"])("warns in %s", (environment) => {
    render(<EnvironmentBanner environment={environment} />)
    expect(screen.getByRole("status")).toHaveTextContent(environment.toUpperCase())
    expect(screen.getByRole("status")).toHaveTextContent("Not for production clinical use")
  })
})
