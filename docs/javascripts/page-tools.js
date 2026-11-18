// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/* Accessible mobile navigation and expandable documentation diagrams. */
(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector(".wy-nav-side");
    const menu = document.querySelector(".docs-mobile-menu");
    if (sidebar && menu) {
      sidebar.id = "docs-sidebar";
      const reflect = () => menu.setAttribute("aria-expanded", String(sidebar.classList.contains("shift")));
      new MutationObserver(reflect).observe(sidebar, { attributes: true, attributeFilter: ["class"] });
      reflect();
    }
    const content = document.querySelector(".rst-content");
    if (!content) return;
    content.querySelectorAll('img[src*="assets/diagrams/"]').forEach(image => {
      const figure = document.createElement("figure");
      figure.className = "docs-figure";
      image.before(figure);
      figure.append(image);
      const caption = document.createElement("figcaption");
      const text = document.createElement("span");
      text.textContent = image.alt;
      const expand = document.createElement("button");
      expand.type = "button";
      expand.textContent = "Expand diagram";
      expand.setAttribute("aria-label", `Expand diagram: ${image.alt}`);
      caption.append(text, expand);
      figure.append(caption);
      expand.addEventListener("click", () => {
        const dialog = document.createElement("dialog");
        dialog.className = "docs-diagram-dialog";
        dialog.setAttribute("aria-label", image.alt || "Expanded diagram");
        const close = document.createElement("button");
        close.type = "button";
        close.textContent = "Close diagram";
        close.addEventListener("click", () => dialog.close());
        const original = document.createElement("a");
        original.href = image.src;
        original.textContent = "Open original SVG";
        original.target = "_blank";
        original.rel = "noopener";
        const toolbar = document.createElement("div");
        toolbar.className = "docs-diagram-toolbar";
        toolbar.append(original, close);
        const canvas = document.createElement("div");
        canvas.className = "docs-diagram-canvas";
        canvas.append(image.cloneNode());
        dialog.append(toolbar, canvas);
        dialog.addEventListener("close", () => { dialog.remove(); expand.focus(); }, { once: true });
        document.body.append(dialog);
        dialog.showModal();
        close.focus();
      });
    });
    if (location.hash) {
      requestAnimationFrame(() => {
        try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView(); }
        catch { /* A malformed external fragment does not prevent reading. */ }
      });
    }
  });
})();
