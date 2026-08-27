import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SurfacePanel, MetricCard } from "@/components/cards/Panel";
import { ExpandableText } from "./ExpandableText";
import { RotatableImage } from "./RotatableImage";
import { PageShell } from "@/components/layout/PageShell";

describe("detail presentation components", () => {
  afterEach(() => vi.useRealTimers());

  it("renders page and surface headings, actions, descriptions, and metrics", () => {
    const { container } = render(
      <PageShell
        eyebrow="Clinical"
        title="Finding"
        description="Review context"
        actions={<button>Save</button>}
      >
        <SurfacePanel
          title="Evidence"
          description="Curated sources"
          actions={<button>Refresh</button>}
        >
          <MetricCard title="Depth" value="500x" sub="Case sample" />
        </SurfacePanel>
      </PageShell>,
    );
    expect(screen.getByText("Clinical")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Finding" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeVisible();
    expect(screen.getByText("500x")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save" })).toBeVisible();
    expect(container.firstElementChild).toHaveClass(
      "page-shell-fluid",
      "responsive-page-padding",
      "responsive-section-gap",
      "3xl:content-ultrawide",
    );
  });

  it("expands, collapses, and copies long text", async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const { container } = render(
      <ExpandableText text="abcdefghijklmnopqrstuvwxyz" maxLength={10} />,
    );

    const value = screen.getByText("abcdefghij...");
    expect(value).toBeVisible();
    expect(value).toHaveClass("min-w-0", "flex-1", "whitespace-normal", "[overflow-wrap:anywhere]");
    expect(container.firstElementChild).toHaveClass("min-w-0", "max-w-full", "overflow-hidden");
    fireEvent.click(screen.getByTitle("Expand"));
    expect(screen.getByText("abcdefghijklmnopqrstuvwxyz")).toBeVisible();
    fireEvent.click(screen.getByTitle("Copy to clipboard"));
    expect(writeText).toHaveBeenCalledWith("abcdefghijklmnopqrstuvwxyz");
    expect(screen.getByTitle("Copy to clipboard")).toHaveClass("text-pass");
    vi.advanceTimersByTime(2000);
    fireEvent.click(screen.getByTitle("Collapse"));
    expect(screen.getByText("abcdefghij...")).toBeVisible();
  });

  it("renders missing text without expansion controls", () => {
    render(<ExpandableText text="-" />);
    expect(screen.getByText("-")).toBeVisible();
    expect(screen.queryByTitle("Expand")).not.toBeInTheDocument();
  });

  it("supports linked images and an explicit image failure state", () => {
    render(
      <RotatableImage src="/profile.png" alt="CNV profile" href="/profile.png" rotation={90} />,
    );
    const image = screen.getByAltText("CNV profile");
    expect(image.closest("a")).toHaveAttribute("href", "/profile.png");
    fireEvent.error(image);
    expect(screen.getByText("The CNV profile image could not be loaded.")).toBeVisible();
  });
});
