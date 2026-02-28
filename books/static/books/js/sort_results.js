 (function () {
    const openBtn = document.getElementById("filtersOpen");
    const closeBtn = document.getElementById("filtersClose");
    const aside = document.getElementById("filtersAside");
    const overlay = document.getElementById("filtersOverlay");
    if (!openBtn || !aside || !overlay) return;

    const isMobile = () => window.matchMedia("(max-width: 1023px)").matches;

    function openAside() {
      if (!isMobile()) return;
      overlay.classList.remove("hidden");
      aside.classList.remove("translate-x-full");
      aside.classList.add("translate-x-0");
      openBtn.setAttribute("aria-expanded", "true");
      document.body.classList.add("overflow-hidden");
    }

    function closeAside() {
      if (!isMobile()) return;
      aside.classList.add("translate-x-full");
      aside.classList.remove("translate-x-0");
      overlay.classList.add("hidden");
      openBtn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("overflow-hidden");
    }

    openBtn.addEventListener("click", () => {
      const expanded = openBtn.getAttribute("aria-expanded") === "true";
      expanded ? closeAside() : openAside();
    });

    closeBtn?.addEventListener("click", closeAside);
    overlay.addEventListener("click", closeAside);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && openBtn.getAttribute("aria-expanded") === "true") {
        closeAside();
      }
    });

    window.addEventListener("resize", () => {
      if (!isMobile()) {
        overlay.classList.add("hidden");
        document.body.classList.remove("overflow-hidden");
        openBtn.setAttribute("aria-expanded", "false");
      }
    });

  })();