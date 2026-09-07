import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  FusionCallerBadges,
  FusionEffectBadge,
  FusionEvidenceBadges,
} from "./fusion-ui"

describe("Fusion UI", () => {
  describe("FusionCallerBadges", () => {
    it("renders empty state", () => {
      render(<FusionCallerBadges callers={null} />)
      expect(screen.getByText("-")).toBeInTheDocument()
    })

    it("renders unique normalized callers", () => {
      const { container } = render(<FusionCallerBadges callers="arriba,StarFusion,Arriba" />)
      expect(screen.getByText("arriba")).toBeInTheDocument()
      expect(screen.getByText("starfusion")).toBeInTheDocument()
      // should deduplicate "arriba"
      expect(screen.getAllByText("arriba")).toHaveLength(1)
      expect(container.querySelector('[data-slot="table-badge"]')).toBeInTheDocument()
      expect(container.querySelector(".text-\\[0\\.4375rem\\]")).not.toBeInTheDocument()
    })
  })

  describe("FusionEffectBadge", () => {
    it("renders empty state", () => {
      render(<FusionEffectBadge effect={null} />)
      expect(screen.getByText("-")).toBeInTheDocument()
    })

    it("renders in-frame with pass severity", () => {
      const { container } = render(<FusionEffectBadge effect="in-frame" />)
      expect(screen.getByText("in-frame")).toBeInTheDocument()
      // Test the pass severity mapped to color-ok
      expect(container.querySelector('.matte-badge-pass')).toBeInTheDocument()
      expect(container.querySelector('[data-slot="table-badge"]')).toBeInTheDocument()
    })

    it("renders out-of-frame with fail severity", () => {
      const { container } = render(<FusionEffectBadge effect="out-of-frame" />)
      expect(screen.getByText("out-of-frame")).toBeInTheDocument()
      expect(container.querySelector('.matte-badge-fail')).toBeInTheDocument()
    })
  })

  describe("FusionEvidenceBadges", () => {
    const metadata = {
      important: ["cancer"],
      not_important: ["artifact"],
      context: ["polya"],
    }

    it("renders empty state", () => {
      render(<FusionEvidenceBadges description={null} />)
      expect(screen.getByText("-")).toBeInTheDocument()
    })

    it("renders badges with mapped severities", () => {
      const { container } = render(
        <FusionEvidenceBadges
          description="cancer,artifact,polya,unknown"
          metadata={metadata}
        />
      )

      expect(screen.getByText("cancer")).toBeInTheDocument()
      expect(container.querySelector('.matte-badge-pass')).toBeInTheDocument() // cancer

      expect(screen.getByText("artifact")).toBeInTheDocument()
      expect(container.querySelector('.matte-badge-fail')).toBeInTheDocument() // artifact

      expect(screen.getByText("polya")).toBeInTheDocument()
      // polya and unknown both get neutral in different forms, but let's check for polya text
      expect(container.querySelectorAll('[data-slot="table-badge"]')).toHaveLength(4)
    })

    it("renders every evidence tag as an individual badge", () => {
      render(
        <FusionEvidenceBadges
          description="a, b, c, d, e"
          metadata={{}}
        />
      )
      expect(screen.getByText("a")).toBeInTheDocument()
      expect(screen.getByText("b")).toBeInTheDocument()
      expect(screen.getByText("c")).toBeInTheDocument()
      expect(screen.getByText("d")).toBeInTheDocument()
      expect(screen.getByText("e")).toBeInTheDocument()
      expect(screen.queryByText("+2")).not.toBeInTheDocument()
    })
  })
})
