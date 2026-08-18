(function exposeAutocomplete() {
  function initAutocomplete({ input, endpoint, onSelect, debounce = 250 }) {
    const root = input.closest('[data-inventory-autocomplete]');
    const list = root?.querySelector('[role="listbox"]');
    const clearButton = root?.querySelector('.search-clear');
    if (!root || !list || root.dataset.autocompleteReady) return;
    root.dataset.autocompleteReady = 'true';

    let suggestions = [];
    let activeIndex = -1;
    let timer;
    let controller;
    let requestNumber = 0;
    let loadingTimer;

    const close = () => {
      clearTimeout(loadingTimer);
      list.hidden = true;
      list.replaceChildren();
      suggestions = [];
      activeIndex = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    };

    const open = () => {
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };

    const renderMessage = (message) => {
      const row = document.createElement('div');
      row.className = 'autocomplete-message';
      row.textContent = message;
      list.replaceChildren(row);
      open();
    };

    const setActive = (index) => {
      const options = [...list.querySelectorAll('[role="option"]')];
      options.forEach((option) => option.setAttribute('aria-selected', 'false'));
      activeIndex = index;
      if (index < 0 || !options[index]) {
        input.removeAttribute('aria-activedescendant');
        return;
      }
      const option = options[index];
      option.setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({ block: 'nearest' });
    };

    const select = (suggestion) => {
      controller?.abort();
      requestNumber += 1;
      input.value = suggestion.name;
      clearButton.hidden = false;
      close();
      onSelect(suggestion);
    };

    const appendHighlightedName = (container, name, query) => {
      const index = name.toLocaleLowerCase().indexOf(query.toLocaleLowerCase());
      if (index < 0) {
        container.textContent = name;
        return;
      }
      container.append(document.createTextNode(name.slice(0, index)));
      const match = document.createElement('strong');
      match.textContent = name.slice(index, index + query.length);
      container.append(match, document.createTextNode(name.slice(index + query.length)));
    };

    const render = (query, results) => {
      list.replaceChildren();
      suggestions = results.slice(0, 10);
      activeIndex = -1;
      if (!suggestions.length) {
        renderMessage('No matching inventory items');
        return;
      }
      suggestions.forEach((suggestion, index) => {
        const row = document.createElement('div');
        row.id = `${list.id}-option-${index}`;
        row.className = 'autocomplete-option';
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', 'false');
        const name = document.createElement('div');
        name.className = 'autocomplete-name';
        appendHighlightedName(name, String(suggestion.name), query);
        const meta = document.createElement('div');
        meta.className = 'autocomplete-meta';
        meta.textContent = `${suggestion.store} · Qty: ${suggestion.quantity}`;
        row.append(name, meta);
        row.addEventListener('pointermove', () => setActive(index));
        row.addEventListener('mousedown', (event) => event.preventDefault());
        row.addEventListener('click', () => select(suggestion));
        list.append(row);
      });
      open();
    };

    const fetchSuggestions = async (query, sequence) => {
      controller?.abort();
      controller = new AbortController();
      loadingTimer = setTimeout(() => renderMessage('Searching…'), 500);
      try {
        const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, {
          signal: controller.signal,
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('Suggestion request failed');
        const data = await response.json();
        if (sequence === requestNumber && input.value.trim() === query) {
          render(query, Array.isArray(data.suggestions) ? data.suggestions : []);
        }
      } catch (error) {
        if (error.name !== 'AbortError' && sequence === requestNumber) close();
      } finally {
        clearTimeout(loadingTimer);
      }
    };

    input.addEventListener('input', () => {
      const query = input.value.trim();
      clearButton.hidden = !input.value;
      clearTimeout(timer);
      controller?.abort();
      requestNumber += 1;
      if (query.length < 2) {
        close();
        if (!query) onSelect(null);
        return;
      }
      const sequence = requestNumber;
      timer = setTimeout(() => fetchSuggestions(query, sequence), debounce);
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' && suggestions.length) {
        event.preventDefault();
        setActive((activeIndex + 1) % suggestions.length);
      } else if (event.key === 'ArrowUp' && suggestions.length) {
        event.preventDefault();
        setActive(activeIndex <= 0 ? suggestions.length - 1 : activeIndex - 1);
      } else if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        select(suggestions[activeIndex]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        controller?.abort();
        requestNumber += 1;
        close();
      }
    });

    clearButton.addEventListener('click', () => {
      input.value = '';
      clearButton.hidden = true;
      controller?.abort();
      clearTimeout(timer);
      close();
      input.focus();
      onSelect(null);
    });
    document.addEventListener('pointerdown', (event) => {
      if (!root.contains(event.target)) {
        controller?.abort();
        requestNumber += 1;
        close();
      }
    });
  }

  window.initAutocomplete = initAutocomplete;
}());
