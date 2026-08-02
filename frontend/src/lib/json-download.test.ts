import { downloadJson, withoutMongoIdentifiers } from "./json-download"
import { describe, expect, it, vi } from "vitest"

describe("JSON download", () => {
  it("removes Mongo identifiers recursively without changing other fields", () => {
    expect(withoutMongoIdentifiers({
      _id: "root",
      name: "sample",
      nested: { _id: "nested", value: 2 },
      items: [{ _id: "item", value: 3 }, null, "text"],
    })).toEqual({
      name: "sample",
      nested: { value: 2 },
      items: [{ value: 3 }, null, "text"],
    })
  })

  it("creates, clicks, and revokes a sanitized JSON download", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    const create = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test")
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)

    downloadJson("sample", { _id: "secret", name: "S1" })

    expect(create).toHaveBeenCalledOnce()
    const blob = create.mock.calls[0][0] as Blob
    expect(await blob.text()).toBe('{\n  "name": "S1"\n}\n')
    expect(click).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith("blob:test")
  })
})
