  // Pagination script 

  const currentPage = {}; // Track current pages for multiple tables

  function displayPage(page, tableBodyId, rowsPerPage) {
    const tableBody = document.getElementById(tableBodyId);
    if (!tableBody) return; // Ensure the table body exists
    const rows = Array.from(tableBody.getElementsByTagName('tr'));
    const totalPages = Math.ceil(rows.length / rowsPerPage);

    // Ensure page number is within range
    if (page < 1 || page > totalPages) return;

    // Hide and show rows based on the current page
    rows.forEach((row, index) => {
      row.style.display = index >= (page - 1) * rowsPerPage && index < page * rowsPerPage ? '' : 'none';
    });

    // Update page info
    const pageInfo = document.querySelector(`[data-page-info="${tableBodyId}"]`);
    if (pageInfo) {
      pageInfo.textContent = `Page ${page} of ${totalPages}`;
    }

    // Enable/disable navigation buttons
    const prevButton = document.querySelector(`[data-prev="${tableBodyId}"]`);
    const nextButton = document.querySelector(`[data-next="${tableBodyId}"]`);

    if (rows.length <= rowsPerPage) {
      if (prevButton) prevButton.style.display = 'none';
      if (nextButton) nextButton.style.display = 'none';
    } else {
      if (prevButton) prevButton.style.display = page === 1 ? 'none' : 'inline-block';
      if (nextButton) nextButton.style.display = page === totalPages ? 'none' : 'inline-block';
    }

    // Update the current page for the table
    currentPage[tableBodyId] = page;
  }

  function prevPage(tableBodyId, rowsPerPage) {
    const page = currentPage[tableBodyId] || 1;
    if (page > 1) {
      displayPage(page - 1, tableBodyId, rowsPerPage);
    }
  }

  function nextPage(tableBodyId, rowsPerPage) {
    const tableBody = document.getElementById(tableBodyId);
    if (!tableBody) return;
    const rows = Array.from(tableBody.getElementsByTagName('tr'));
    const totalPages = Math.ceil(rows.length / rowsPerPage);

    const page = currentPage[tableBodyId] || 1;
    if (page < totalPages) {
      displayPage(page + 1, tableBodyId, rowsPerPage);
    }
  }

  // Initialize pagination based on elements with class "pagination"
  function initializePagination() {
    document.querySelectorAll('.pagination').forEach((paginationElement) => {
      const table = paginationElement.querySelector('table tbody');
      if (!table) return;

      const tableBodyId = table.id;
      const rowsPerPage = parseInt(paginationElement.getAttribute('data-rows-per-page'), 10) || 10;
      const buttonColor = paginationElement.getAttribute('pagination-button-color') || 'blue';
      const buttonTextColor = paginationElement.getAttribute('pagination-button-text-color') || 'white';
      const rows = Array.from(table.getElementsByTagName('tr'));

      // Only apply pagination if rows exceed the limit
      if (rows.length > rowsPerPage) {
        currentPage[tableBodyId] = 1;

        // Create pagination controls
        const paginationControls = document.createElement('div');
        paginationControls.className = 'flex flex-wrap justify-between mt-1 break-all';

        paginationControls.innerHTML = `
          <button class="bg-${buttonColor}-400 text-${buttonTextColor} py-1 px-2 rounded-lg disabled:opacity-50" data-prev="${tableBodyId}" onclick="prevPage('${tableBodyId}', ${rowsPerPage})">Previous</button>
          <span class="mx-3 mb-1" data-page-info="${tableBodyId}">Page 1 of ${Math.ceil(rows.length / rowsPerPage)}</span>
          <button class="bg-${buttonColor}-400 text-${buttonTextColor} py-1 px-2  rounded-lg  disabled:opacity-50" data-next="${tableBodyId}" onclick="nextPage('${tableBodyId}', ${rowsPerPage})">Next</button>
        `;

        paginationElement.appendChild(paginationControls);

        // Initialize first page
        displayPage(1, tableBodyId, rowsPerPage);
      }
    });
  }

  // Run initialization when DOM is fully loaded
  document.addEventListener('DOMContentLoaded', initializePagination);
