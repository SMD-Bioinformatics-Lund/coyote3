/* Keep short field names and status columns together; descriptions retain wrapping. */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".rst-content table").forEach((table) => {
    const rows = Array.from(table.rows);
    if (!rows.length || rows.some((row) =>
      Array.from(row.cells).some((cell) => cell.colSpan !== 1 || cell.rowSpan !== 1))) return;
    let budget = 50;
    const columns = Array.from(rows[0].cells, (_, index) => {
      const cells = rows.map((row) => row.cells[index]).filter(Boolean);
      const lengths = cells.map((cell) => cell.textContent.trim().length);
      return { cells, length: Math.max(...lengths), index };
    });
    // Give the smallest columns priority so descriptive columns retain most of the width.
    columns.sort((a, b) => a.length - b.length).forEach(({ cells, length, index }) => {
      if (length > (index === 0 ? 32 : 18) || length > budget) return;
      if (cells.some((cell) => cell.querySelector("br, p, ul, ol, pre"))) return;
      cells.forEach((cell) => cell.classList.add("docs-compact-column"));
      budget -= length;
    });
  });
});
