(function () {
  function initAssayNavigation() {
    const currentUrl = new URL(window.location.href);
    const path = currentUrl.pathname.split("/").filter(Boolean);
    const selectedType = currentUrl.searchParams.get("panel_type") || path[1] || null;
    const selectedTech = currentUrl.searchParams.get("panel_tech") || path[2] || null;
    const selectedGroup = currentUrl.searchParams.get("assay_group") || path[3] || null;

    const sections = document.querySelectorAll(".assay-group-section");
    const toggles = document.querySelectorAll('[id^="toggle-"]');
    const pills = document.querySelectorAll("#assay-pills a");

    function showType(type) {
      sections.forEach((section) => section.classList.toggle("hidden", section.dataset.type !== type));
      toggles.forEach((toggle) => {
        const active = toggle.id === `toggle-${type}`;
        toggle.classList.toggle("bg-orange-300", active);
        toggle.classList.toggle("text-black", active);
        toggle.classList.toggle("font-bold", active);
        toggle.classList.toggle("bg-indigo-200", !active);
      });
    }

    function highlightPill() {
      pills.forEach((pill) => {
        const pillUrl = new URL(pill.href, window.location.origin);
        const pillPathParts = pillUrl.pathname.split("/").filter(Boolean);
        const pillType = pillUrl.searchParams.get("panel_type") || pillPathParts[1] || null;
        const pillTech = pillUrl.searchParams.get("panel_tech") || pillPathParts[2] || null;
        const pillGroup = pillUrl.searchParams.get("assay_group") || pillPathParts[3] || null;
        const match =
          !!selectedType &&
          !!selectedTech &&
          !!selectedGroup &&
          (pillType || "").toLowerCase() === selectedType.toLowerCase() &&
          (pillTech || "").toLowerCase() === selectedTech.toLowerCase() &&
          (pillGroup || "").toLowerCase() === selectedGroup.toLowerCase();
        pill.classList.toggle("bg-orange-300", match);
        pill.classList.toggle("text-black", match);
        pill.classList.toggle("border-yellow-600", match);
        if (!match) {
          pill.classList.remove("bg-orange-300", "text-black", "border-yellow-600");
          pill.classList.add(
            "bg-gray-100",
            "hover:bg-orange-200",
            "text-gray-800",
            "border-transparent",
          );
        }
      });
    }

    if (selectedType) {
      showType(selectedType);
      highlightPill();
    }

    toggles.forEach((button) => {
      button.addEventListener("click", (event) => {
        const type = button.id.replace("toggle-", "");
        showType(type);
        event.stopPropagation();
      });
    });

    document.addEventListener("click", (event) => {
      if (!event.target.closest("#assay-pills") && !event.target.closest('[id^="toggle-"]')) {
        const matchExists = Array.from(pills).some((pill) => {
          const pillUrl = new URL(pill.href, window.location.origin);
          return (
            (pillUrl.searchParams.get("panel_type") || "").toLowerCase() ===
              (selectedType || "").toLowerCase() &&
            (pillUrl.searchParams.get("panel_tech") || "").toLowerCase() ===
              (selectedTech || "").toLowerCase() &&
            (pillUrl.searchParams.get("assay_group") || "").toLowerCase() ===
              (selectedGroup || "").toLowerCase()
          );
        });
        if (!matchExists) {
          sections.forEach((section) => section.classList.add("hidden"));
          toggles.forEach((toggle) =>
            toggle.classList.remove("bg-orange-300", "text-black", "font-bold"),
          );
        }
      }
    });
  }

  function showActionModal({
    url,
    form,
    title = "Confirm Action",
    message = "Are you sure you want to proceed?",
    confirmText = "Confirm",
    confirmColor = "blue",
    onConfirm,
  }) {
    const modal = document.getElementById("actionModal");
    const titleEl = document.getElementById("actionModalTitle");
    const messageEl = document.getElementById("actionModalMessage");
    const confirmBtn = document.getElementById("actionModalConfirm");
    if (!modal || !titleEl || !messageEl || !confirmBtn) {
      return;
    }

    titleEl.textContent = title;
    messageEl.innerHTML = message;
    confirmBtn.textContent = confirmText;
    modal.dataset.actionUrl = url || "";
    modal.__actionForm = form || null;
    modal.__actionOnConfirm = typeof onConfirm === "function" ? onConfirm : null;

    const confirmColorMap = {
      blue: "bg-blue-600 hover:bg-blue-700",
      red: "bg-red-600 hover:bg-red-700",
      green: "bg-green-600 hover:bg-green-700",
      yellow: "bg-yellow-600 hover:bg-yellow-700",
      orange: "bg-orange-600 hover:bg-orange-700",
      purple: "bg-purple-600 hover:bg-purple-700",
      gray: "bg-gray-600 hover:bg-gray-700",
    };
    const confirmClasses = confirmColorMap[confirmColor] || confirmColorMap.blue;
    confirmBtn.className = `${confirmClasses} text-white font-medium py-2 px-4 rounded-lg shadow-lg transition`;

    modal.classList.remove("hidden");
  }

  function hideActionModal() {
    const modal = document.getElementById("actionModal");
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.dataset.actionUrl = "";
    modal.__actionForm = null;
    modal.__actionOnConfirm = null;
  }

  function initActionModal() {
    const modal = document.getElementById("actionModal");
    const cancelButton = document.getElementById("actionModalCancel");
    const closeButton = document.getElementById("actionModalClose");
    const confirmButton = document.getElementById("actionModalConfirm");
    if (!modal || !cancelButton || !confirmButton || !closeButton) {
      return;
    }

    async function runModalAction() {
      const callback = modal.__actionOnConfirm;
      const form = modal.__actionForm;
      const url = modal.dataset.actionUrl;
      if (callback) {
        hideActionModal();
        await callback();
        return;
      }
      if (form) {
        hideActionModal();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
        return;
      }
      if (url) {
        hideActionModal();
        window.location.assign(url);
      }
    }

    function openFormActionModal(form) {
      showActionModal({
        form,
        title: form.dataset.actionModalTitle || "Confirm Action",
        message: form.dataset.actionModalMessage || "Are you sure you want to proceed?",
        confirmText: form.dataset.actionModalConfirmText || "Confirm",
        confirmColor: form.dataset.actionModalConfirmColor || "blue",
      });
    }

    document.addEventListener("submit", (event) => {
      const form = event.target.closest("form[data-action-modal-form]");
      if (!form) {
        return;
      }
      event.preventDefault();
      openFormActionModal(form);
    });

    if (!cancelButton) {
      return;
    }
    cancelButton.addEventListener("click", hideActionModal);
    closeButton.addEventListener("click", hideActionModal);
    confirmButton.addEventListener("click", async (event) => {
      event.preventDefault();
      await runModalAction();
    });
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        hideActionModal();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        hideActionModal();
      }
    });
  }

  function initUserMenu() {
    const userMenuButton = document.getElementById("userMenuButton");
    const userDropdown = document.getElementById("userDropdown");
    if (!userMenuButton || !userDropdown) {
      return;
    }
    userMenuButton.addEventListener("click", (event) => {
      event.stopPropagation();
      userDropdown.classList.toggle("hidden");
    });

    window.addEventListener("click", () => {
      if (!userDropdown.classList.contains("hidden")) {
        userDropdown.classList.add("hidden");
      }
    });

    userDropdown.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  function initFlashMessages() {
    const alerts = document.querySelectorAll(".flash-message");
    alerts.forEach((alert, index) => {
      let timeoutId;

      function startTimeout() {
        timeoutId = window.setTimeout(() => {
          alert.classList.remove("translate-x-0", "opacity-100");
          alert.classList.add("translate-x-full", "opacity-0");
          window.setTimeout(() => {
            alert.style.display = "none";
          }, 500);
        }, 7000 + index * 100);
      }

      window.setTimeout(() => {
        alert.classList.remove("translate-x-full", "opacity-0");
        alert.classList.add("translate-x-0", "opacity-100");
        startTimeout();
      }, 100 + index * 100);

      alert.addEventListener("mouseenter", () => window.clearTimeout(timeoutId));
      alert.addEventListener("mouseleave", startTimeout);

      alert.querySelector(".close-btn")?.addEventListener("click", () => {
        window.clearTimeout(timeoutId);
        alert.classList.remove("translate-x-0", "opacity-100");
        alert.classList.add("translate-x-full", "opacity-0");
        window.setTimeout(() => {
          alert.style.display = "none";
        }, 500);
      });
    });
  }

  function showTooltip(event, content) {
    let tooltip = document.getElementById("global-tooltip");

    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.id = "global-tooltip";
      tooltip.className =
        "fixed bg-black text-white text-xs rounded-md shadow-lg p-2 w-auto max-w-xs opacity-0 transition-all duration-200 z-50 pointer-events-none";
      document.body.appendChild(tooltip);
    }

    tooltip.innerHTML = content;
    tooltip.style.opacity = "1";
    tooltip.style.pointerEvents = "auto";

    let x = event.clientX + 15;
    let y = event.clientY + 15;

    if (x + tooltip.offsetWidth > window.innerWidth) {
      x = event.clientX - tooltip.offsetWidth - 15;
    }
    if (y + tooltip.offsetHeight > window.innerHeight) {
      y = event.clientY - tooltip.offsetHeight - 15;
    }

    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;

    event.target.addEventListener("mouseleave", function hideTooltip() {
      tooltip.style.opacity = "0";
      tooltip.style.pointerEvents = "none";
      event.target.removeEventListener("mouseleave", hideTooltip);
    });
  }

  function toggleLongText(button) {
    const target = button.dataset.target;
    const short = document.getElementById(`${target}-short`);
    const full = document.getElementById(`${target}-full`);
    if (!short || !full) {
      return;
    }

    const isShortVisible = !short.classList.contains("hidden");
    short.classList.toggle("hidden", isShortVisible);
    full.classList.toggle("hidden", !isShortVisible);
    button.innerText = isShortVisible ? "[−]" : "[+]";
  }

  function initTextToggleButtons() {
    document.querySelectorAll(".text-toggle").forEach((button) => {
      const target = button.dataset.target;
      const shortEl = document.getElementById(`${target}-short`);
      if (shortEl && shortEl.scrollWidth > shortEl.clientWidth) {
        button.classList.remove("hidden");
      }
    });
  }

  function initAutoclick() {
    if (typeof window.$ !== "function") {
      return;
    }
    window.$('[data-autoclick="true"]').click();
    window.$('[data-autoclick="true"]').click();
  }

  function renderLocalTimestamps() {
    const nodes = document.querySelectorAll("time.js-local-datetime[datetime]");
    for (const node of nodes) {
      const raw = node.getAttribute("datetime");
      if (!raw) {
        continue;
      }
      const dt = new Date(raw);
      if (Number.isNaN(dt.getTime())) {
        continue;
      }

      const mode = (node.dataset.localTime || "relative").toLowerCase();
      if (mode === "absolute") {
        node.textContent = dt.toLocaleString();
      } else {
        const seconds = Math.round((dt.getTime() - Date.now()) / 1000);
        const absSeconds = Math.abs(seconds);
        let value = seconds;
        let unit = "second";
        if (absSeconds >= 31536000) {
          value = Math.round(seconds / 31536000);
          unit = "year";
        } else if (absSeconds >= 2592000) {
          value = Math.round(seconds / 2592000);
          unit = "month";
        } else if (absSeconds >= 86400) {
          value = Math.round(seconds / 86400);
          unit = "day";
        } else if (absSeconds >= 3600) {
          value = Math.round(seconds / 3600);
          unit = "hour";
        } else if (absSeconds >= 60) {
          value = Math.round(seconds / 60);
          unit = "minute";
        }
        node.textContent = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(
          value,
          unit,
        );
      }
      node.setAttribute("title", dt.toLocaleString());
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initAssayNavigation();
    initActionModal();
    initUserMenu();
    initFlashMessages();
    initTextToggleButtons();
    initAutoclick();
    renderLocalTimestamps();
  });

  window.showActionModal = showActionModal;
  window.showTooltip = showTooltip;
  window.toggleLongText = toggleLongText;
})();
