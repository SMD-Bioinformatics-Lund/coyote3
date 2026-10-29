import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConfigurationTransfer } from "./ConfigurationTransfer"
import { downloadJson } from "@/lib/json-download"

vi.mock("@/lib/json-download", () => ({ downloadJson: vi.fn() }))

function upload(value: string, size?: number) {
  const file = new File([value], "config.json", { type: "application/json" })
  Object.defineProperty(file, "text", { value: async () => value })
  if (size !== undefined) Object.defineProperty(file, "size", { value: size })
  fireEvent.change(screen.getByLabelText("Import configuration JSON"), { target: { files: [file] } })
}

it("stages a JSON object and exports the supplied portable document", async () => {
  const onImport = vi.fn()
  render(<ConfigurationTransfer label="configuration" filename="config" document={{ name: "Example" }}
    onImport={onImport} fields={["name"]} required={["name"]} />)
  upload('{"name":"Example"}')
  await waitFor(() => expect(onImport).toHaveBeenCalledWith({ name: "Example" }))
  fireEvent.click(screen.getByRole("button", { name: "Export JSON" }))
  expect(downloadJson).toHaveBeenCalledWith("config", { name: "Example" })
})

it.each([
  ["{", "not valid JSON"],
  ["[]", "JSON object"],
  ['{"unexpected":true}', "Unsupported fields: unexpected"],
  ["{}", "Missing fields: name"],
])("rejects invalid or governed input without staging it: %s", async (source, message) => {
  const onImport = vi.fn()
  render(<ConfigurationTransfer label="configuration" filename="config" onImport={onImport}
    fields={["name"]} required={["name"]} />)
  upload(source)
  expect(await screen.findByRole("alert")).toHaveTextContent(message)
  expect(onImport).not.toHaveBeenCalled()
})

it("rejects oversized files and surfaces asynchronous validation failures", async () => {
  const onImport = vi.fn().mockRejectedValue(new Error("Scope is unavailable"))
  render(<ConfigurationTransfer label="configuration" filename="config" onImport={onImport} />)
  upload("{}", 1024 * 1024 + 1)
  expect(await screen.findByRole("alert")).toHaveTextContent("1 MiB")
  expect(onImport).not.toHaveBeenCalled()
  upload("{}")
  expect(await screen.findByRole("alert")).toHaveTextContent("Scope is unavailable")
  expect(screen.getByRole("button", { name: "Import JSON" })).toBeEnabled()
})

it("does not offer import without its authorized handler", () => {
  render(<ConfigurationTransfer label="configuration" filename="config" document={{}} />)
  expect(screen.queryByRole("button", { name: "Import JSON" })).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Export JSON" })).toBeEnabled()
})

it("ignores audit metadata on import and exports it only with explicit opt-in", async () => {
  const onImport = vi.fn()
  render(<ConfigurationTransfer label="configuration" filename="config" document={{ name: "Example" }}
    metadataDocument={{ name: "Example", created_by: "author", version: 3, status: "published" }}
    onImport={onImport} fields={["name"]} required={["name"]} />)
  upload('{"name":"Example","created_by":"other","version":99,"status":"published"}')
  await waitFor(() => expect(onImport).toHaveBeenCalledWith({ name: "Example" }))
  expect(screen.getByLabelText("Include metadata")).not.toBeChecked()
  fireEvent.click(screen.getByRole("button", { name: "Export JSON" }))
  expect(downloadJson).toHaveBeenLastCalledWith("config", { name: "Example" })
  fireEvent.click(screen.getByLabelText("Include metadata"))
  fireEvent.click(screen.getByRole("button", { name: "Export JSON" }))
  expect(downloadJson).toHaveBeenLastCalledWith("config", {
    name: "Example", created_by: "author", version: 3, status: "published",
  })
})
