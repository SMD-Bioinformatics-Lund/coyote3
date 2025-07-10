/*
 * Copyright (c) 2025 Coyote3 Project Authors
 * All rights reserved.
 *
 * This source file is part of the Coyote3 codebase.
 * The Coyote3 project provides a framework for genomic data analysis,
 * interpretation, reporting, and clinical diagnostics.
 *
 * Unauthorized use, distribution, or modification of this software or its
 * components is strictly prohibited without prior written permission from
 * the copyright holders.
 *
 */

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
        if (!value) return "mixed";
    
        if (!isNaN(parseFloat(value)) && value.match(/^-?\d+(\.\d+)?$/)) return "number";
        if (Date.parse(value)) return "date";
        if (value.toLowerCase().match(/^(\d+|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago$/)) {
            return "relative-time";
        }
        if (value.match(/^\d+:\d+$/)) {
            return "chr-pos";
        }
        if (value.match(/^\d+:\d+-\d+$/)) {
            return "chr-region";
        }
        return "mixed";
    }
    
    

    // Function to parse mixed values (separating numbers & text)
    function parseMixedValue(value) {
        const lower = value.trim().toLowerCase();
    
        // Relative time
        if (lower.match(/^(\d+|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago$/)) {
            return { relative: parseRelativeTime(lower), text: lower };
        }
    
        // Chromosome:position
        if (lower.match(/^\d+:\d+$/)) {
            const [chr, pos] = lower.split(":").map(Number);
            return { chr, pos };
        }
    
        // Chromosome:start-end
        if (lower.match(/^\d+:\d+-\d+$/)) {
            const [chrPart, range] = lower.split(":");
            const [start, end] = range.split("-").map(Number);
            return {
                chr: parseInt(chrPart),
                start,
                end
            };
        }
    
        // Natural alphanumeric fallback
        let match = lower.match(/^(\d+(?:\.\d+)?)(.*)$/);
        let numberPart = match ? parseFloat(match[1]) : null;
        let textPart = match ? match[2] : lower;
    
        return {
            number: isNaN(numberPart) ? null : numberPart,
            text: textPart.trim()
        };
    }

    // Function to compare mixed values (number-first sorting)
    function compareMixed(a, b) {
        if ("chr" in a && "start" in a && "end" in a && "chr" in b && "start" in b && "end" in b) {
            if (a.chr !== b.chr) return a.chr - b.chr;
            if (a.start !== b.start) return a.start - b.start;
            return a.end - b.end;
        }        
        if ("chr" in a && "pos" in a && "chr" in b && "pos" in b) {
            if (a.chr !== b.chr) return a.chr - b.chr;
            return a.pos - b.pos;
        }        
        if ("relative" in a && "relative" in b) {
            return a.relative - b.relative;
        }
    
        if (a.number !== null && b.number !== null) {
            return a.number - b.number;
        }
    
        if (a.number !== null) return -1;
        if (b.number !== null) return 1;
    
        return a.text.localeCompare(b.text);
    }
    

    // Function to parse relative time strings
    function parseRelativeTime(value) {
        const match = value.match(/^(\d+|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago$/i);
        if (!match) return Infinity;
    
        let amount = match[1];
        const unit = match[2];
    
        amount = (amount === "a" || amount === "an") ? 1 : parseInt(amount);
    
        const msPerUnit = {
            second: 1000,
            minute: 60 * 1000,
            hour: 60 * 60 * 1000,
            day: 24 * 60 * 60 * 1000,
            week: 7 * 24 * 60 * 60 * 1000,
            month: 30 * 24 * 60 * 60 * 1000,
            year: 365 * 24 * 60 * 60 * 1000,
        };
    
        return Date.now() - amount * msPerUnit[unit];
    }
});
