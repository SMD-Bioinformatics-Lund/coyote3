import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { loadScript } from "./helpers/loadScript.mjs";

/**
 * pagination.js declares displayPage / prevPage / nextPage / initializePagination
 * as top-level function declarations, which become globals when the file is
 * injected as a classic <script>. We test through the DOM by building a
 * .pagination wrapper and firing DOMContentLoaded.
 */
function buildPagination({ rows, rowsPerPage }) {
  const trs = Array.from({ length: rows }, (_, i) => `<tr><td>row${i + 1}</td></tr>`).join("");
  document.body.innerHTML = `
    <div class="pagination" data-rows-per-page="${rowsPerPage}">
      <table>
        <tbody id="tbody-test">${trs}</tbody>
      </table>
    </div>
  `;
}

function visibleRowTexts() {
  return Array.from(document.querySelectorAll("#tbody-test tr"))
    .filter((tr) => tr.style.display !== "none")
    .map((tr) => tr.textContent.trim());
}

function pageInfoText() {
  const el = document.querySelector('[data-page-info="tbody-test"]');
  return el ? el.textContent.trim() : null;
}

describe("pagination.js", () => {
  beforeAll(() => {
    loadScript("pagination.js", {
      exports: ["displayPage", "prevPage", "nextPage", "initializePagination"],
    });
  });

  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("does not render controls when row count is at or below the limit", () => {
    buildPagination({ rows: 5, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    expect(document.querySelector('[data-page-info="tbody-test"]')).toBeNull();
    expect(visibleRowTexts()).toHaveLength(5);
  });

  it("renders pagination controls when rows exceed the limit", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    expect(document.querySelector('[data-prev="tbody-test"]')).not.toBeNull();
    expect(document.querySelector('[data-next="tbody-test"]')).not.toBeNull();
    expect(pageInfoText()).toBe("Page 1 of 3");
  });

  it("displays only the first page on initial render", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    const visible = visibleRowTexts();
    expect(visible).toHaveLength(10);
    expect(visible[0]).toBe("row1");
    expect(visible[9]).toBe("row10");
  });

  it("nextPage advances to the next slice and updates the page info", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    window.nextPage("tbody-test", 10);
    const visible = visibleRowTexts();
    expect(visible[0]).toBe("row11");
    expect(visible[9]).toBe("row20");
    expect(pageInfoText()).toBe("Page 2 of 3");
  });

  it("prevPage goes back to the previous slice", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    window.nextPage("tbody-test", 10);
    window.nextPage("tbody-test", 10);
    expect(pageInfoText()).toBe("Page 3 of 3");
    window.prevPage("tbody-test", 10);
    expect(pageInfoText()).toBe("Page 2 of 3");
    expect(visibleRowTexts()[0]).toBe("row11");
  });

  it("hides Prev on the first page and Next on the last page", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    const prev = document.querySelector('[data-prev="tbody-test"]');
    const next = document.querySelector('[data-next="tbody-test"]');
    expect(prev.style.display).toBe("none"); // first page
    expect(next.style.display).toBe("inline-block");

    window.nextPage("tbody-test", 10);
    window.nextPage("tbody-test", 10);
    expect(pageInfoText()).toBe("Page 3 of 3");
    expect(prev.style.display).toBe("inline-block");
    expect(next.style.display).toBe("none"); // last page
  });

  it("ignores out-of-range page requests", () => {
    buildPagination({ rows: 25, rowsPerPage: 10 });
    document.dispatchEvent(new Event("DOMContentLoaded"));
    window.displayPage(99, "tbody-test", 10);
    expect(pageInfoText()).toBe("Page 1 of 3");
    expect(visibleRowTexts()[0]).toBe("row1");
  });

  it("returns gracefully when called with an unknown table id", () => {
    document.body.innerHTML = "";
    expect(() => window.displayPage(1, "missing", 10)).not.toThrow();
    expect(() => window.nextPage("missing", 10)).not.toThrow();
    expect(() => window.prevPage("missing", 10)).not.toThrow();
  });
});
