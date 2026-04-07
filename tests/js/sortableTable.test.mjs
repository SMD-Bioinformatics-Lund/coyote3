import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { loadScript } from "./helpers/loadScript.mjs";

/**
 * sortableTable.js attaches its sort handlers inside a DOMContentLoaded
 * listener and keeps its helpers in a closure. We test it through the DOM:
 * build a table, fire DOMContentLoaded so handlers attach, then click the
 * header and assert the resulting row order.
 */
function buildTable(rows) {
  document.body.innerHTML = `
    <table>
      <thead class="sortable">
        <tr><th data-default-order="asc">Col</th></tr>
      </thead>
      <tbody>
        ${rows.map((cell) => `<tr><td>${cell}</td></tr>`).join("")}
      </tbody>
    </table>
  `;
}

function clickHeader() {
  document.querySelector("thead.sortable th").click();
}

function visibleOrder() {
  return Array.from(document.querySelectorAll("tbody tr td")).map((td) =>
    td.textContent.trim(),
  );
}

describe("sortableTable.js", () => {
  beforeAll(() => {
    loadScript("sortableTable.js");
  });

  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("sorts plain numbers ascending then descending", () => {
    buildTable(["10", "2", "33", "5"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    clickHeader(); // first click → asc (default)
    expect(visibleOrder()).toEqual(["2", "5", "10", "33"]);
    clickHeader(); // second click → desc
    expect(visibleOrder()).toEqual(["33", "10", "5", "2"]);
  });

  it("sorts chromosome:position values numerically by chr then pos", () => {
    buildTable(["10:500", "2:100", "10:200", "2:9000"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    clickHeader();
    expect(visibleOrder()).toEqual(["2:100", "2:9000", "10:200", "10:500"]);
  });

  it("sorts chromosome:start-end ranges by chr, start, end", () => {
    buildTable(["10:200-300", "2:100-500", "10:200-250", "2:50-60"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    clickHeader();
    expect(visibleOrder()).toEqual([
      "2:50-60",
      "2:100-500",
      "10:200-250",
      "10:200-300",
    ]);
  });

  it("sorts mixed alphanumeric values via locale comparison", () => {
    // None of these start with a digit, so parseMixedValue falls through to
    // text.localeCompare which orders alphabetically: "alpha" < "item1" <
    // "item10" < "item2".
    buildTable(["item10", "item2", "item1", "alpha"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    clickHeader();
    expect(visibleOrder()).toEqual(["alpha", "item1", "item10", "item2"]);
  });

  it("sorts relative time values from oldest to newest when ascending", () => {
    buildTable(["2 hours ago", "5 minutes ago", "1 day ago", "a week ago"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    clickHeader();
    expect(visibleOrder()).toEqual([
      "a week ago",
      "1 day ago",
      "2 hours ago",
      "5 minutes ago",
    ]);
  });

  it("toggles the sort arrow indicator visibility on first click", () => {
    buildTable(["b", "a", "c"]);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    const arrow = document.querySelector("thead.sortable th .sort-arrow");
    expect(arrow.classList.contains("hidden")).toBe(true);
    clickHeader();
    expect(arrow.classList.contains("hidden")).toBe(false);
    expect(arrow.innerHTML).toBe("▲");
  });

  it("respects data-nosort and skips sorting that header", () => {
    document.body.innerHTML = `
      <table>
        <thead class="sortable">
          <tr><th data-nosort>NoSort</th></tr>
        </thead>
        <tbody>
          <tr><td>b</td></tr>
          <tr><td>a</td></tr>
        </tbody>
      </table>
    `;
    document.dispatchEvent(new Event("DOMContentLoaded"));
    document.querySelector("thead.sortable th").click();
    expect(visibleOrder()).toEqual(["b", "a"]); // unchanged
    expect(document.querySelector("thead.sortable th .sort-arrow")).toBeNull();
  });
});
