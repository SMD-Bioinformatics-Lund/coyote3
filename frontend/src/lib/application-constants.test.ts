// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { describe, expect, it } from "vitest"

import {
  NOMENCLATURE_CODES,
  nomenclatureLabel,
} from "./application-constants"
import { NOMENCLATURE_METADATA } from "./defaults"

describe("application constants", () => {
  it("defines nomenclature codes and display labels from one mapping", () => {
    expect(NOMENCLATURE_CODES).toEqual(["p", "c", "g", "cn", "f", "t"])
    expect(NOMENCLATURE_METADATA.cn.label).toBe("Copy number (cn)")
    expect(nomenclatureLabel("p")).toBe("Protein (p)")
    expect(nomenclatureLabel("F")).toBe("Fusion (f)")
  })

  it("preserves unknown values and represents missing values consistently", () => {
    expect(nomenclatureLabel("custom")).toBe("custom")
    expect(nomenclatureLabel(null)).toBe("-")
  })
})
