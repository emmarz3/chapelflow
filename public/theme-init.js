(() => {
  try {
    document.documentElement.dataset.theme = localStorage.getItem("chapelflow-theme") === "dark" ? "dark" : "light";
  } catch { /* The default light theme remains available without storage. */ }
  if (location.pathname !== "/") return;
  let seen = false;
  try { seen = sessionStorage.getItem("chapelflow:intro-seen") === "1"; }
  catch { /* Storage can be unavailable; the intro still runs. */ }
  if (!seen) document.documentElement.dataset.introEntry = "true";
})();
