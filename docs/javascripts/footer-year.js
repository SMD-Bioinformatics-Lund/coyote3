/* Keep the displayed year current without rebuilding the deployed documentation. */
function updateCopyrightYear() {
  const year = String(new Date().getFullYear());
  document.querySelectorAll("[data-current-year]").forEach((element) => {
    element.textContent = year;
  });
}

updateCopyrightYear();
window.addEventListener("pageshow", updateCopyrightYear);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) updateCopyrightYear();
});
