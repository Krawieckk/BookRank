(function () {
  function initReviewToggles(root = document) {
    const blocks = root.querySelectorAll(".review-text");
    blocks.forEach((p) => {
      const full = p.dataset.full ?? "";
      const limit = parseInt(p.dataset.limit || "320", 10);
      const btn = p.parentElement?.querySelector(".review-toggle");

      if (!btn) return;

      if (p.dataset.inited === "1") return;
      p.dataset.inited = "1";

      if (full.length <= limit) {
        p.textContent = full;
        btn.classList.add("hidden");
        return;
      }

      const truncated = full.slice(0, limit).trimEnd() + "…";
      let expanded = false;

      p.textContent = truncated;
      btn.classList.remove("hidden");
      btn.setAttribute("aria-expanded", "false");
      btn.textContent = "Show more";

      btn.addEventListener("click", () => {
        expanded = !expanded;
        p.textContent = expanded ? full : truncated;
        btn.textContent = expanded ? "Show less" : "Show more";
        btn.setAttribute("aria-expanded", expanded ? "true" : "false");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => initReviewToggles());

  document.body.addEventListener("htmx:afterSwap", (e) => {
    initReviewToggles(e.target);
  });
})();