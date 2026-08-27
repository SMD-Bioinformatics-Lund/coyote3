import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import {
  RuntimeExecutionSummary,
  ControlToggle,
} from "./runtime-panels"

describe("Runtime Panels UI", () => {
  describe("RuntimeExecutionSummary", () => {
    it("renders ready state", () => {
      render(
        <RuntimeExecutionSummary
          configuredEnabled={true}
          executionState="ready"
          workersOnline={2}
        />
      )
      expect(screen.getByText("Execution is allowed and workers are responding")).toBeInTheDocument()
      expect(screen.getByText(/2 workers can accept work/)).toBeInTheDocument()
    })

    it("renders workers missing state", () => {
      render(
        <RuntimeExecutionSummary
          configuredEnabled={true}
          executionState="workers_missing"
          workersOnline={0}
        />
      )
      expect(screen.getByText("Execution is allowed, but no workers responded")).toBeInTheDocument()
    })

    it("renders execution disabled with workers online", () => {
      render(
        <RuntimeExecutionSummary
          configuredEnabled={false}
          executionState="execution_disabled_workers_online"
          workersOnline={1}
        />
      )
      expect(screen.getByText("Application task execution is disabled")).toBeInTheDocument()
      expect(screen.getByText(/1 worker remains online/)).toBeInTheDocument()
    })

    it("renders execution disabled", () => {
      render(
        <RuntimeExecutionSummary
          configuredEnabled={false}
          executionState="execution_disabled"
          workersOnline={0}
        />
      )
      expect(screen.getByText("Application task execution is disabled")).toBeInTheDocument()
      expect(screen.getByText(/No workers responded/)).toBeInTheDocument()
    })

    it("renders unavailable state", () => {
      render(
        <RuntimeExecutionSummary
          configuredEnabled={true}
          executionState="unavailable"
          workersOnline={0}
        />
      )
      expect(screen.getByText("Runtime execution state is unavailable")).toBeInTheDocument()
    })
  })

  describe("ControlToggle", () => {
    const mockDef = {
      label: "Test Control",
      summary: "This is a test control",
      enabledEffect: "Does X",
      disabledEffect: "Does Y",
      operationalNote: "Note Z",
    }

    it("renders checked state and calls onChange", () => {
      const onChange = vi.fn()
      render(
        <ControlToggle
          definition={mockDef}
          checked={true}
          onChange={onChange}
        />
      )

      expect(screen.getByText("Test Control")).toBeInTheDocument()

      const button = screen.getByRole("switch")
      expect(button).toHaveAttribute("aria-checked", "true")

      fireEvent.click(button)
      expect(onChange).toHaveBeenCalledWith(false)
    })

    it("renders unchecked state and handles disabled", () => {
      render(
        <ControlToggle
          definition={mockDef}
          checked={false}
          onChange={vi.fn()}
          disabled={true}
        />
      )

      const button = screen.getByRole("switch")
      expect(button).toHaveAttribute("aria-checked", "false")
      expect(button).toBeDisabled()
    })
  })
})
