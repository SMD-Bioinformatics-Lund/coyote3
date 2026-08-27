import { describe, expect, it } from "vitest"

import { tieringIsEnabled, type ApplicationModulesPayload } from "@/lib/app-module-state"

describe("tieringIsEnabled", () => {
  it("uses clinically conservative defaults when runtime controls are unavailable", () => {
    expect(tieringIsEnabled(undefined, "small_variant")).toBe(true)
    expect(tieringIsEnabled(undefined, "fusion")).toBe(true)
    expect(tieringIsEnabled(undefined, "cnv")).toBe(false)
    expect(tieringIsEnabled(undefined, "translocation")).toBe(false)
  })

  it("uses the database-backed runtime setting when supplied", () => {
    const payload: ApplicationModulesPayload = {
      modules: {},
      curation: {
        tiering: {
          small_variant: false,
          cnv: true,
          fusion: false,
          translocation: true,
        },
      },
    }

    expect(tieringIsEnabled(payload, "small_variant")).toBe(false)
    expect(tieringIsEnabled(payload, "cnv")).toBe(true)
    expect(tieringIsEnabled(payload, "fusion")).toBe(false)
    expect(tieringIsEnabled(payload, "translocation")).toBe(true)
  })
})
