import { renderHook } from "@testing-library/react"
import { expect, it } from "vitest"
import { useRuleWorkspaceLayout } from "./useRuleWorkspaceLayout"

it("bounds restored clinical widths so corrupt storage cannot hide the workspace", () => {
  localStorage.setItem("clinical-rules-width:Resize rule-set list", "100000")
  localStorage.setItem("clinical-rules-width:Resize text preview", "1")
  const { result } = renderHook(() => useRuleWorkspaceLayout("clinical"))
  expect(result.current.listWidth).toBe(440)
  expect(result.current.previewWidth).toBeGreaterThanOrEqual(280)
})
