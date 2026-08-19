(function initializeInventorySearch() {
  function applySearch(root) {
    const form = root.closest('form');
    if (!form) return;
    // A GET form naturally preserves the current store and alphabet controls.
    form.requestSubmit();
  }

  async function clearSearch(root) {
    const form = root.closest('form');
    const panel = root.closest('.inventory-panel, .lookup-panel');
    if (!form || !panel) return;

    const url = new URL(form.action || window.location.href, window.location.href);
    const params = new URLSearchParams(new FormData(form));
    params.delete('search');
    url.search = params.toString();
    root.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(url, { headers: { 'X-Inventory-Refresh': '1' } });
      if (!response.ok) throw new Error('Search clear failed');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const updatedPanel = page.querySelector(panel.matches('.inventory-panel')
        ? '.inventory-panel'
        : '.lookup-panel');
      if (!updatedPanel) throw new Error('Search results were missing');

      ['.alphabet', '.table-wrap', '.table-footer'].forEach((selector) => {
        const current = panel.querySelector(selector);
        const updated = updatedPanel.querySelector(selector);
        if (current && updated) current.replaceWith(updated);
      });
      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    } catch (_error) {
      // Keep the cleared, focused search field usable if the update cannot be loaded.
    } finally {
      root.removeAttribute('aria-busy');
    }
  }

  function initialize() {
    document.querySelectorAll('[data-inventory-autocomplete]').forEach((root) => {
      window.initAutocomplete({
        input: root.querySelector('input[name="search"]'),
        endpoint: '/api/inventory/suggestions',
        onSelect: () => applySearch(root),
        onClear: () => clearSearch(root),
      });
    });
  }

  initialize();
  document.addEventListener('pantrypilot:inventory-refreshed', initialize);
}());
