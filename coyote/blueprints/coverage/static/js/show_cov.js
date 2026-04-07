(function () {
  function parseJsonDataset(element, key, fallback) {
    const raw = element.dataset[key];
    if (!raw) {
      return fallback;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      console.error(`Failed to parse coverage dataset key "${key}"`, error);
      return fallback;
    }
  }

  function initCoveragePage(root) {
    const geneData = parseJsonDataset(root, "coveragePayload", { genes: {} });
    const depthCutoff = Number(root.dataset.depthCutoff || 0);
    const sampleAssay = root.dataset.sampleGroup || "";
    const updateGeneStatusUrl = root.dataset.updateGeneStatusUrl;
    const splitLayout = document.getElementById("coverage-split-layout");
    const sidebar = document.getElementById("coverage-sidebar");
    const collapseBtn = document.getElementById("collapse-sidebar-btn");
    const expandBtn = document.getElementById("expand-sidebar-btn");
    const resizeHandle = document.getElementById("coverage-resize-handle");
    const sortableTable = document.getElementById("sortable-table");
    const selectionHint = document.getElementById("selection-hint");
    const plotContainerRoot = document.getElementById("plot-container");
    const dataContainerRoot = document.getElementById("data-container");

    window.currentCoveragePlotReflow = null;

    function sendDataToBackend(gene, coord, region, status) {
      const payload = { gene, region, coord, status, smp_grp: sampleAssay };
      fetch(updateGeneStatusUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          alert(`Success:${data.message}`);
        })
        .catch((error) => {
          console.error("Error:", error);
        });
    }

    function blacklistRegion(gene, coord, region) {
      sendDataToBackend(gene, coord, region, "blacklist");
    }

    function plotGene(gene) {
      const selectedGene = geneData.genes?.[gene];
      if (!selectedGene) {
        console.error(`Gene ${gene} not found in the data.`);
        return;
      }

      selectionHint?.classList.add("hidden");
      plotContainerRoot?.classList.remove("hidden");
      dataContainerRoot?.classList.remove("hidden");

      d3.select("#plot-container").select("#gene-plot-container").remove();

      const plotContainer = d3
        .select("#plot-container")
        .append("div")
        .attr("id", "gene-plot-container")
        .attr("class", "space-y-3");

      const heading = plotContainer
        .append("div")
        .attr("class", "flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 pb-2");

      heading
        .append("h3")
        .attr("class", "text-sm font-semibold uppercase tracking-wide text-gray-800")
        .text(`Gene: ${gene} @ ${depthCutoff}X`);

      const actions = heading.append("div").attr("class", "flex flex-wrap items-center gap-2");

      const zoomOutBtn = actions
        .append("button")
        .attr("type", "button")
        .attr(
          "class",
          "inline-flex items-center rounded-md border border-indigo-200 bg-white px-2 py-1 text-xs font-semibold text-gray-700 transition hover:bg-gray-100",
        )
        .text("Zoom Out");

      const zoomInBtn = actions
        .append("button")
        .attr("type", "button")
        .attr(
          "class",
          "inline-flex items-center rounded-md border border-indigo-200 bg-white px-2 py-1 text-xs font-semibold text-gray-700 transition hover:bg-gray-100",
        )
        .text("Zoom In");

      const zoomResetBtn = actions
        .append("button")
        .attr("type", "button")
        .attr(
          "class",
          "inline-flex items-center rounded-md border border-indigo-200 bg-white px-2 py-1 text-xs font-semibold text-gray-700 transition hover:bg-gray-100",
        )
        .text("Reset");

      const zoomLabel = actions
        .append("span")
        .attr(
          "class",
          "rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800",
        )
        .text("100%");

      actions
        .append("button")
        .attr(
          "class",
          "inline-flex items-center rounded-md border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-100",
        )
        .text("Blacklist Gene")
        .on("click", () => blacklistRegion(gene, "", ""));

      const geneStart = selectedGene.transcript.start;
      const geneEnd = selectedGene.transcript.end;
      const svgHeight = 190;
      const margin = { top: 20, right: 40, bottom: 24, left: 60 };
      const plotHeight = svgHeight - margin.top - margin.bottom;
      const minZoom = 0.5;
      const maxZoom = 8;
      let currentZoom = 1;
      let basePlotWidth = 900;

      const svgWrap = plotContainer
        .append("div")
        .attr("class", "max-w-full overflow-x-auto overflow-y-hidden rounded-md border border-cyan-200 bg-white p-1");

      function updateBasePlotWidth() {
        const host = svgWrap.node();
        const hostWidth = host?.clientWidth || 900;
        basePlotWidth = Math.max(hostWidth - 8, 520);
      }

      function renderGenePlotSvg() {
        updateBasePlotWidth();
        const svgWidth = Math.max(Math.floor(basePlotWidth * currentZoom), 520);
        zoomLabel.text(`${Math.round(currentZoom * 100)}%`);
        svgWrap.selectAll("*").remove();

        const svg = svgWrap.append("svg").attr("width", svgWidth).attr("height", svgHeight);

        const xScale = d3
          .scaleLinear()
          .domain([geneStart, geneEnd])
          .range([margin.left, svgWidth - margin.right]);

        const geneY = plotHeight / 2 + 24;

        svg
          .append("line")
          .style("stroke", "#111827")
          .style("stroke-width", 1)
          .attr("x1", xScale(selectedGene.transcript.start))
          .attr("y1", geneY)
          .attr("x2", xScale(selectedGene.transcript.end))
          .attr("y2", geneY);

        svg
          .selectAll("exon")
          .data(selectedGene.exons)
          .enter()
          .append("rect")
          .style("fill", "#d1d5db")
          .attr("x", (datum) => xScale(datum.start))
          .attr("y", geneY - 10)
          .attr("width", (datum) => xScale(datum.end) - xScale(datum.start))
          .attr("height", 20)
          .append("title")
          .text(
            (datum) =>
              `${datum.chr}:${datum.start}-${datum.end} (Exon ${datum.nbr}), Cov: ${Number(datum.cov).toFixed(2)}`,
          );

        svg
          .selectAll("cds")
          .data(selectedGene.CDS)
          .enter()
          .append("rect")
          .attr("fill", (datum) => {
            if (Number.isNaN(datum.cov)) {
              return "#111827";
            }
            return datum.cov < depthCutoff ? "#fda4af" : "#86efac";
          })
          .attr("x", (datum) => xScale(datum.start))
          .attr("y", geneY - 10)
          .attr("width", (datum) => xScale(datum.end) - xScale(datum.start))
          .attr("height", 20)
          .append("title")
          .text(
            (datum) =>
              `${datum.chr}:${datum.start}-${datum.end} (Exon ${datum.nbr}), Cov: ${Number(datum.cov).toFixed(2)}`,
          );

        svg
          .selectAll("probes")
          .data(selectedGene.probes)
          .enter()
          .append("rect")
          .attr("fill", (datum) => (datum.cov < depthCutoff ? "#fda4af" : "#93c5fd"))
          .attr("x", (datum) => xScale(datum.start))
          .attr("y", geneY - 35)
          .attr("width", (datum) => xScale(datum.end) - xScale(datum.start))
          .attr("height", 20)
          .append("title")
          .text((datum) => `${datum.chr}:${datum.start}-${datum.end}, Cov: ${Number(datum.cov).toFixed(2)}X`);
      }

      const legendData = [
        { color: "#fda4af", label: `Any coverage < ${depthCutoff}` },
        { color: "#93c5fd", label: `Probe coverage >= ${depthCutoff}` },
        { color: "#86efac", label: `CDS coverage >= ${depthCutoff}` },
        { color: "#111827", label: "Not covered by design" },
      ];

      const legend = plotContainer
        .append("div")
        .attr(
          "class",
          "flex flex-wrap items-center gap-3 rounded-md border border-indigo-100 bg-white px-3 py-2 text-xs text-gray-700",
        );

      legendData.forEach((item) => {
        const legendItem = legend.append("div").attr("class", "inline-flex items-center gap-2");
        legendItem
          .append("span")
          .attr("class", "inline-block h-3.5 w-3.5 rounded-sm border border-indigo-200")
          .style("background-color", item.color);
        legendItem.append("span").text(item.label);
      });

      zoomInBtn.on("click", () => {
        currentZoom = Math.min(maxZoom, Number((currentZoom * 1.25).toFixed(2)));
        renderGenePlotSvg();
      });

      zoomOutBtn.on("click", () => {
        currentZoom = Math.max(minZoom, Number((currentZoom / 1.25).toFixed(2)));
        renderGenePlotSvg();
      });

      zoomResetBtn.on("click", () => {
        currentZoom = 1;
        renderGenePlotSvg();
      });

      window.currentCoveragePlotReflow = function () {
        renderGenePlotSvg();
      };

      renderGenePlotSvg();

      d3.select("#data-container").select("#gene-data-container").remove();

      const dataContainer = d3
        .select("#data-container")
        .append("div")
        .attr("id", "gene-data-container")
        .attr("class", "space-y-4");

      const lowCoverageExons = selectedGene.CDS.filter((datum) => datum.cov < depthCutoff);
      const lowCoverageProbes = selectedGene.probes.filter((datum) => datum.cov < depthCutoff);
      if (lowCoverageExons.length === 0 && lowCoverageProbes.length === 0) {
        dataContainer
          .append("div")
          .attr(
            "class",
            "rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800",
          )
          .text("No low coverage exons or probes below the selected cutoff for this gene.");
        return;
      }

      const tabsWrap = dataContainer.append("div").attr("class", "space-y-3");
      const tabButtons = tabsWrap
        .append("div")
        .attr("class", "flex items-center gap-2 border-b border-indigo-100 pb-2");
      const tabPanels = tabsWrap.append("div");

      function makeTablePanel({ title, columns, rows, region, showExonColumn }) {
        const panel = tabPanels.append("div").attr("class", "hidden rounded-md border border-indigo-100 bg-white");

        panel
          .append("div")
          .attr(
            "class",
            "border-b border-indigo-100 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-700",
          )
          .text(title);

        const scroll = panel.append("div").attr("class", "max-h-80 overflow-auto");
        const table = scroll.append("table").attr("class", "min-w-full table-auto text-xs text-gray-800");
        const thead = table.append("thead");
        thead
          .append("tr")
          .selectAll("th")
          .data(columns)
          .enter()
          .append("th")
          .attr(
            "class",
            "border-b border-indigo-200 bg-slate-100 px-3 py-2 text-left text-[11px] uppercase font-semibold text-gray-600",
          )
          .text((column) => column);

        const tbody = table.append("tbody");
        rows.forEach((entry) => {
          const coord = `${entry.chr}:${entry.start}-${entry.end}`;
          const row = tbody.append("tr").attr("class", "hover:bg-blue-50");
          if (showExonColumn) {
            row.append("td").attr("class", "border-b border-indigo-100 px-3 py-2").text(`${entry.nbr}`);
          }
          row.append("td").attr("class", "border-b border-indigo-100 px-3 py-2").text(coord);
          row
            .append("td")
            .attr("class", "border-b border-indigo-100 px-3 py-2")
            .text(`${Number(entry.cov).toFixed(2)}X`);
          row
            .append("td")
            .attr("class", "border-b border-indigo-100 px-3 py-2")
            .append("button")
            .attr(
              "class",
              "inline-flex items-center rounded-md border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-100",
            )
            .text("Blacklist")
            .on("click", () => blacklistRegion(gene, coord, region));
        });

        return panel;
      }

      const tabs = [];
      if (lowCoverageExons.length > 0) {
        tabs.push({
          key: "exons",
          label: `Exons (${lowCoverageExons.length})`,
          panel: makeTablePanel({
            title: "Exons Not Meeting Criteria",
            columns: ["Exon", "Coordinates", "Coverage", "Actions"],
            rows: lowCoverageExons,
            region: "CDS",
            showExonColumn: true,
          }),
        });
      }
      if (lowCoverageProbes.length > 0) {
        tabs.push({
          key: "probes",
          label: `Probes (${lowCoverageProbes.length})`,
          panel: makeTablePanel({
            title: "Probes Not Meeting Criteria",
            columns: ["Coordinates", "Coverage", "Actions"],
            rows: lowCoverageProbes,
            region: "probe",
            showExonColumn: false,
          }),
        });
      }

      function activateTab(activeKey) {
        tabs.forEach((tab) => {
          tab.button.attr(
            "class",
            tab.key === activeKey
              ? "rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-800"
              : "rounded-md border border-indigo-200 bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-100",
          );
          tab.panel.classed("hidden", tab.key !== activeKey);
        });
      }

      tabs.forEach((tab) => {
        tab.button = tabButtons
          .append("button")
          .attr("type", "button")
          .text(tab.label)
          .on("click", () => activateTab(tab.key));
      });

      activateTab(tabs[0].key);
    }

    function setCollapsed(collapsed) {
      if (!splitLayout || !collapseBtn || !expandBtn || !sidebar || !resizeHandle) {
        return;
      }
      splitLayout.dataset.collapsed = collapsed ? "true" : "false";
      collapseBtn.classList.toggle("hidden", collapsed);
      expandBtn.classList.toggle("hidden", !collapsed);
      sidebar.classList.toggle("hidden", collapsed);
      sidebar.classList.toggle("md:block", !collapsed);
      [
        "md:w-0",
        "md:max-w-0",
        "md:min-w-0",
        "md:p-0",
        "md:border-0",
        "overflow-hidden",
      ].forEach((cssClass) => {
        sidebar.classList.toggle(cssClass, collapsed);
      });
      ["md:w-[28%]", "md:min-w-[280px]", "md:max-w-[30%]"].forEach((cssClass) => {
        sidebar.classList.toggle(cssClass, !collapsed);
      });
      resizeHandle.classList.toggle("hidden", collapsed);
      resizeHandle.classList.toggle("md:block", !collapsed);
      if (typeof window.currentCoveragePlotReflow === "function") {
        window.currentCoveragePlotReflow();
      }
    }

    collapseBtn?.addEventListener("click", () => setCollapsed(true));
    expandBtn?.addEventListener("click", () => setCollapsed(false));

    let isResizing = false;
    resizeHandle?.addEventListener("mousedown", (event) => {
      if (!splitLayout || window.innerWidth < 768 || splitLayout.dataset.collapsed === "true") {
        return;
      }
      isResizing = true;
      event.preventDefault();
    });

    window.addEventListener("mousemove", (event) => {
      if (!isResizing || !splitLayout) {
        return;
      }

      const layoutRect = splitLayout.getBoundingClientRect();
      const pointerOffset = event.clientX - layoutRect.left;
      const nextPercent = (pointerOffset / layoutRect.width) * 100;
      const clampedPercent = Math.max(18, Math.min(30, nextPercent));
      splitLayout.style.setProperty("--coverage-sidebar-width", `${clampedPercent}%`);
      if (typeof window.currentCoveragePlotReflow === "function") {
        window.currentCoveragePlotReflow();
      }
    });

    window.addEventListener("mouseup", () => {
      isResizing = false;
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth < 768 && splitLayout?.dataset.collapsed === "true") {
        setCollapsed(false);
      }
      if (typeof window.currentCoveragePlotReflow === "function") {
        window.currentCoveragePlotReflow();
      }
    });

    sortableTable?.addEventListener("click", (event) => {
      const geneButton = event.target.closest("[data-plot-gene]");
      if (geneButton) {
        plotGene(geneButton.dataset.plotGene);
        return;
      }

      const header = event.target.closest("th[data-column][data-type]");
      if (!header || !sortableTable.contains(header)) {
        return;
      }

      const columnIndex = Number(header.getAttribute("data-column"));
      const type = header.getAttribute("data-type");
      const tbody = sortableTable.querySelector("tbody");
      if (!tbody) {
        return;
      }
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const isAscending = header.getAttribute("data-order") === "asc";
      header.setAttribute("data-order", isAscending ? "desc" : "asc");

      const sortedRows = rows.sort((rowA, rowB) => {
        let aValue = rowA.children[columnIndex].textContent.trim();
        let bValue = rowB.children[columnIndex].textContent.trim();
        if (type === "number") {
          aValue = parseFloat(aValue) || 0;
          bValue = parseFloat(bValue) || 0;
        }
        return isAscending ? (aValue > bValue ? 1 : -1) : (aValue < bValue ? 1 : -1);
      });

      tbody.innerHTML = "";
      sortedRows.forEach((row) => tbody.appendChild(row));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-coverage-page]").forEach(initCoveragePage);
  });
})();
