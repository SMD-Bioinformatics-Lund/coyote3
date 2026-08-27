import { describe, expect, it } from "vitest"

import {
  analysisLayoutForUser,
  analysisModernViewTriedForUser,
  normalizeUserUiSettings,
  sampleListLayoutForUser,
  sampleListModernViewTriedForUser,
  tablePageSizeForUser,
} from "./user-settings"

describe("analysisLayoutForUser", () => {
  it("uses classic for new and existing users without an explicit preference", () => {
    expect(analysisLayoutForUser(undefined)).toBe("classic")
    expect(analysisLayoutForUser({} as never)).toBe("classic")
  })

  it("returns the persisted modern layout", () => {
    expect(analysisLayoutForUser({ ui_settings: { analysis_layout: "modern" } } as never)).toBe("modern")
  })

  it("uses classic for sample lists until modern is selected", () => {
    expect(sampleListLayoutForUser(undefined)).toBe("classic")
    expect(sampleListLayoutForUser({ ui_settings: { sample_list_layout: "modern" } } as never)).toBe("modern")
  })

  it("tracks modern-view discovery independently for analysis and sample lists", () => {
    expect(analysisModernViewTriedForUser(undefined)).toBe(false)
    expect(sampleListModernViewTriedForUser(undefined)).toBe(false)
    expect(analysisModernViewTriedForUser({
      ui_settings: { analysis_modern_view_tried: true },
    } as never)).toBe(true)
    expect(analysisModernViewTriedForUser({
      ui_settings: { analysis_layout: "modern" },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { sample_list_modern_view_tried: true },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { sample_list_layout: "modern" },
    } as never)).toBe(true)
    expect(sampleListModernViewTriedForUser({
      ui_settings: { analysis_modern_view_tried: true },
    } as never)).toBe(false)
  })

  it("normalizes and resolves the persisted table page size", () => {
    expect(normalizeUserUiSettings(undefined).table_page_size).toBe(50)
    expect(tablePageSizeForUser(undefined)).toBe(50)
    expect(tablePageSizeForUser({ ui_settings: { table_page_size: 100 } } as never)).toBe(100)
    expect(tablePageSizeForUser({ ui_settings: { table_page_size: 500 } } as never)).toBe(50)
  })
})
