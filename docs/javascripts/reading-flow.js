/* Keep optional references reversible; navigation remains ordinary same-tab links. */
(() => {
  const root = new URL("../", document.currentScript.src);
  const key = "coyote3.docs.reference-trail";
  const read = () => {
    try { return JSON.parse(sessionStorage.getItem(key) || "[]").filter(item =>
      new URL(item.from).origin === location.origin && new URL(item.from).pathname.startsWith(root.pathname)); }
    catch { return []; }
  };
  const write = trail => {
    try { sessionStorage.setItem(key, JSON.stringify(trail.slice(-12))); } catch { /* Storage is optional. */ }
  };
  const restoreContext = () => {
    const container = document.getElementById("docs-return-context");
    if (!container) return;
    let trail = read();
    while (trail.length && new URL(trail.at(-1).from).pathname === location.pathname) trail.pop();
    write(trail);
    const current = trail.at(-1);
    container.replaceChildren();
    container.hidden = !current || current.to !== location.pathname;
    if (container.hidden) return;
    const label = document.createElement("span");
    label.textContent = "You opened a reference. ";
    const back = document.createElement("a");
    back.href = current.from;
    back.textContent = `Return to ${current.label}`;
    back.addEventListener("click", () => { trail.pop(); write(trail); });
    container.append(label, back);
  };
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
    content.querySelectorAll("a[href]").forEach((link, index) => {
      if (link.closest("nav, footer, .wy-breadcrumbs, .docs-page-contents") || link.classList.contains("headerlink")) return;
      const destination = new URL(link.href);
      if (destination.origin !== location.origin || !destination.pathname.startsWith(root.pathname)
        || destination.pathname === location.pathname || destination.pathname === root.pathname
        || /\.(svg|png|jpg|pdf|zip)$/.test(destination.pathname)) return;
      link.id ||= `docs-reference-${index}`;
      link.addEventListener("click", event => {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target === "_blank") return;
        const from = new URL(location.href);
        from.hash = link.id;
        const title = content.querySelector("h1")?.textContent.replace(/¶\s*$/, "").trim() || document.title;
        write([...read(), { from: from.href, to: destination.pathname, label: title }]);
      });
    });
    const tools = document.querySelector(".docs-reading-tools");
    if (tools) {
      const measure = () => document.documentElement.style.setProperty("--docs-reading-offset", `${tools.getBoundingClientRect().height + 20}px`);
      new ResizeObserver(measure).observe(tools);
      measure();
    }
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
    restoreContext();
    if (location.hash) {
      requestAnimationFrame(() => {
        try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView(); }
        catch { /* A malformed external fragment does not prevent reading. */ }
      });
    }
  });
  window.addEventListener("pageshow", restoreContext);
})();
