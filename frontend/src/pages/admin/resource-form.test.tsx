import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AdminManagedForm, FormControl } from "./resource-form"
import type { AdminResourceSpec, FormSpec, FormField } from "./resource-specs"

describe("Resource Form UI", () => {
  const dummySpec: AdminResourceSpec = {
    key: "test_resource",
    title: "Test Resource",
    description: "A test resource",
    endpoint: "/test-resources",
    listKey: "items",
    idKeys: ["id"],
    permissions: {
      list: "test:list",
      view: "test:view",
      create: "test:create",
      edit: "test:edit",
      delete: "test:delete",
    },
  }

  const dummyForm: FormSpec = {
    fields: {
      name: {
        data_type: "string",
        display_type: "input",
        required: true,
      },
      status: {
        data_type: "string",
        display_type: "select",
        options: ["active", "inactive"],
      }
    },
    sections: {
      General: ["name", "status"]
    }
  }

  describe("AdminManagedForm", () => {
    it("renders create mode with Save button", () => {
      render(
        <AdminManagedForm
          mode="create"
          spec={dummySpec}
          form={dummyForm}
          values={{}}
          setValues={vi.fn()}
          onSave={vi.fn()}
          onCancel={vi.fn()}
          isSaving={false}
          error=""
        />
      )
      expect(screen.getByText("Create Test Resource")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument()
    })

    it("renders edit mode with Save button", () => {
      render(
        <AdminManagedForm
          mode="edit"
          spec={dummySpec}
          form={dummyForm}
          values={{}}
          setValues={vi.fn()}
          onSave={vi.fn()}
          onCancel={vi.fn()}
          isSaving={false}
          error=""
        />
      )
      expect(screen.getByText("Edit Test Resource")).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument()
    })

    it("renders view mode without Save button", () => {
      render(
        <AdminManagedForm
          mode="view"
          spec={dummySpec}
          form={dummyForm}
          values={{}}
          setValues={vi.fn()}
          onSave={vi.fn()}
          onCancel={vi.fn()}
          isSaving={false}
          error=""
        />
      )
      expect(screen.getByText("View Test Resource")).toBeInTheDocument()
      expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument()
    })

    it("displays error message if provided", () => {
      render(
        <AdminManagedForm
          mode="create"
          spec={dummySpec}
          form={dummyForm}
          values={{}}
          setValues={vi.fn()}
          onSave={vi.fn()}
          onCancel={vi.fn()}
          isSaving={false}
          error="Test validation error"
        />
      )
      expect(screen.getByText("Test validation error")).toBeInTheDocument()
    })
  })

  describe("FormControl", () => {
    it("renders input field and updates value", () => {
      const onChange = vi.fn()
      const field: FormField = { data_type: "string", display_type: "input" }
      render(
        <FormControl
          name="test"
          field={field}
          value="initial"
          mode="edit"
          onChange={onChange}
        />
      )

      const input = screen.getByRole("textbox")
      expect(input).toHaveValue("initial")

      fireEvent.change(input, { target: { value: "updated" } })
      expect(onChange).toHaveBeenCalledWith("updated")
    })

    it("disables input in view mode", () => {
      const field: FormField = { data_type: "string", display_type: "input" }
      render(
        <FormControl
          name="test"
          field={field}
          value="initial"
          mode="view"
          onChange={vi.fn()}
        />
      )

      const input = screen.getByRole("textbox")
      expect(input).toBeDisabled()
    })
  })
})
