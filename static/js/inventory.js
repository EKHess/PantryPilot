(function initializeInventorySearch() {
  function applySearch(root) {
    const form = root.closest('form');
    if (!form) return;
    // A GET form naturally preserves the current store and alphabet controls.
    form.requestSubmit();
  }

  function initialize() {
    document.querySelectorAll('[data-inventory-autocomplete]').forEach((root) => {
      window.initAutocomplete({
        input: root.querySelector('input[name="search"]'),
        endpoint: '/api/inventory/suggestions',
        onSelect: () => applySearch(root),
      });
    });
  }

  initialize();
  document.addEventListener('pantrypilot:inventory-refreshed', initialize);
}());
