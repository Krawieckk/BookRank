document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("search-input");
  const resultsBox = document.getElementById("search-results");

  if (!input || !resultsBox) return;

  const endpoint = input.dataset.endpoint;
  const MIN_LEN = 2;
  const DEBOUNCE_MS = 400;

  let timer = null;
  let lastQuery = "";
  let abortController = null;

  function hideResults() {
    resultsBox.classList.add("hidden");
    resultsBox.innerHTML = "";
  }

  function escapeHtml(str) {
    return str
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderResults(items) {
    if (!items.length) {
      resultsBox.innerHTML = `
        <div class="px-4 py-3 text-sm text-gray-500">
          No results
        </div>
      `;
      resultsBox.classList.remove("hidden");
      return;
    }

    resultsBox.innerHTML = items.map(item => `
      <a href="${escapeHtml(item.url)}"
         class="block px-4 py-2 hover:bg-gray-50">
        <div class="text-sm font-medium text-gray-900">${escapeHtml(item.title)}</div>
        <div class="text-xs text-gray-500">${escapeHtml(item.authors || "")}</div>
      </a>
    `).join("");

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

  document.addEventListener("click", (e) => {
    const isInside =
      e.target.closest("#search-results") ||
      e.target.closest("#search-input");

    if (!isInside) hideResults();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideResults();
  });
});
