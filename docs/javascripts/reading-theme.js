/* Apply the saved reading preference before the page is painted. */
(() => {
  const key = "coyote3-docs-theme";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try {
    const saved = localStorage.getItem(key);
    if (["light", "dark", "system"].includes(saved)) preference = saved;
  } catch { /* Browser storage is optional. */ }
  const apply = () => {
    document.documentElement.dataset.theme = preference === "system"
      ? (system.matches ? "dark" : "light") : preference;
  };
  apply();
  system.addEventListener("change", apply);
  document.addEventListener("DOMContentLoaded", () => {
    const control = document.getElementById("docs-reading-theme");
    if (!control) return;
    control.value = preference;
    control.addEventListener("change", () => {
      preference = control.value;
      try { localStorage.setItem(key, preference); } catch { /* Keep the in-page choice. */ }
      apply();
    });
  });
})();
