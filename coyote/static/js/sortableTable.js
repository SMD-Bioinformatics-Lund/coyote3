document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("thead.sortable th").forEach((header) => {
        // Skip sorting if 'data-nosort' is set
        if (header.hasAttribute("data-nosort")) return;

        // Create sorting arrow (initially hidden)
        let arrow = document.createElement("span");
        arrow.className = "sort-arrow"; // Arrow controlled via CSS
        arrow.innerHTML = "▼"; // Default down arrow
        header.appendChild(arrow);

        header.addEventListener("click", function () {
            let table = header.closest("table");
            let tbody = table.querySelector("tbody");
            let rows = Array.from(tbody.querySelectorAll("tr"));
            let index = Array.from(header.parentNode.children).indexOf(header);

            // Reset sorting for all headers except the clicked one
            document.querySelectorAll("thead.sortable th").forEach((th) => {
                if (th !== header && !th.hasAttribute("data-nosort")) {
                    th.querySelector(".sort-arrow").classList.add("hidden");
                    th.dataset.order = "";
                }
            });

            // Toggle sort order (ascending/descending)
            let currentOrder = header.dataset.order || "none";
            let newOrder = currentOrder === "asc" ? "desc" : "asc";
            header.dataset.order = newOrder;

            // Update arrow visibility and direction
            arrow.innerHTML = newOrder === "asc" ? "▲" : "▼";
            arrow.classList.remove("hidden");

            // Detect column data type
            let firstCellValue = rows[0]?.cells[index]?.textContent.trim();
            let type = detectDataType(firstCellValue);

            rows.sort((rowA, rowB) => {
                let cellA = rowA.cells[index].textContent.trim();
                let cellB = rowB.cells[index].textContent.trim();

                let a = parseMixedValue(cellA);
                let b = parseMixedValue(cellB);

                return newOrder === "asc" ? compareMixed(a, b) : compareMixed(b, a);
            });

            tbody.append(...rows);
        });
    });

    // Function to detect column data type
    function detectDataType(value) {
        if (!isNaN(parseFloat(value)) && value.match(/^-?\d+(\.\d+)?$/)) return "number";
        if (Date.parse(value)) return "date";
        return "mixed"; // Default to mixed sorting
    }

    // Function to parse mixed values (separating numbers & text)
    function parseMixedValue(value) {
        let numberPart = parseFloat(value.match(/^-?\d+(\.\d+)?/)?.[0]); // Extract number if present
        let textPart = value.replace(/^-?\d+(\.\d+)?/, "").trim(); // Extract text if present
        return { number: isNaN(numberPart) ? null : numberPart, text: textPart.toLowerCase() };
    }

    // Function to compare mixed values (number-first sorting)
    function compareMixed(a, b) {
        if (a.number !== null && b.number !== null) {
            return a.number - b.number; // Sort numbers numerically
        }
        if (a.number !== null) return -1; // Numbers come before text
        if (b.number !== null) return 1;  // Text comes after numbers
        return a.text.localeCompare(b.text); // Sort text alphabetically
    }
});
