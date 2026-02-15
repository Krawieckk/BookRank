(function () {
  const MIN_LEN = 2;
  const DEBOUNCE_MS = 400;

  let globalOutsideClickBound = false;

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function initTagsSearch(root = document) {
    const input = root.querySelector("#tags-search-input");
    const resultsBox = root.querySelector("#tags-search-results");
    const form = root.querySelector("#filtersForm") || document.getElementById("filtersForm");

    if (!input || !resultsBox) return;

    if (input.dataset.bound === "1") return;
    input.dataset.bound = "1";

    const endpoint = input.dataset.endpoint;

    let timer = null;
    let lastQuery = "";
    let abortController = null;

    function hideResults() {
      resultsBox.classList.add("hidden");
      resultsBox.innerHTML = "";
    }

    function ensureHiddenMulti(name, value) {
      if (!form) return;

      const v = String(value);
      const existing = form.querySelector(
        `input[type="hidden"][name="${CSS.escape(name)}"][value="${CSS.escape(v)}"]`
      );
      if (existing) return;

      const inp = document.createElement("input");
      inp.type = "hidden";
      inp.name = name;
      inp.value = v;
      form.appendChild(inp);
    }

    function renderResults(items) {
      if (!items.length) {
        resultsBox.innerHTML = `
          <div class="px-3 py-2 text-sm text-gray-500">
            No results
          </div>
        `;
        resultsBox.classList.remove("hidden");
        return;
      }

      resultsBox.innerHTML = items
        .map(
          (item) => `
            <button
              type="button"
              data-tag-id="${escapeHtml(item.id)}"
              class="w-full text-left block px-3 py-1 hover:bg-gray-50">
              <div class="text-sm font-medium text-gray-900">${escapeHtml(item.name)}</div>
            </button>
          `
        )
        .join("");

      resultsBox.classList.remove("hidden");
    }

    async function fetchSuggestions(query) {
      if (abortController) abortController.abort();
      abortController = new AbortController();

      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("q", query);

      const res = await fetch(url.toString(), { signal: abortController.signal });
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || [];
    }

    resultsBox.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-tag-id]");
      if (!btn) return;

      const id = btn.dataset.tagId;

      ensureHiddenMulti("tags", id);

      const pageInput = form?.querySelector('input[name="page"]');
      if (pageInput) pageInput.remove();

      hideResults();
      input.value = "";
      lastQuery = "";

      form?.requestSubmit();
    });

    input.addEventListener("input", () => {
      const query = input.value.trim();

      if (timer) clearTimeout(timer);

      timer = setTimeout(async () => {
        if (query.length < MIN_LEN) {
          lastQuery = query;
          hideResults();
          return;
        }

        if (query === lastQuery) return;
        lastQuery = query;

        try {
          const items = await fetchSuggestions(query);
          renderResults(items);
        } catch (e) {
          if (e.name !== "AbortError") hideResults();
        }
      }, DEBOUNCE_MS);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hideResults();
    });

    if (!globalOutsideClickBound) {
      globalOutsideClickBound = true;
      document.addEventListener("click", (e) => {
        const isInside =
          e.target.closest("#tags-search-results") ||
          e.target.closest("#tags-search-input");
        if (!isInside) {
          const box = document.getElementById("tags-search-results");
          if (box) {
            box.classList.add("hidden");
            box.innerHTML = "";
          }
        }
      });
    }
  }

  // Initial load
  document.addEventListener("DOMContentLoaded", () => initTagsSearch(document));

  if (window.htmx && typeof window.htmx.onLoad === "function") {
    window.htmx.onLoad((content) => {
      initTagsSearch(content);
    });
  }
})();
