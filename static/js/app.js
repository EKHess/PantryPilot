const sidebar = document.querySelector('#sidebar');
const toggle = document.querySelector('.menu-toggle');

toggle?.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  toggle.setAttribute('aria-expanded', String(open));
});

function openModal(modal) {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  (modal.querySelector('input, select') || modal.querySelector('button'))?.focus();
}

function closeModal(modal) {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}

document.querySelectorAll('[data-open-modal]').forEach((button) => button.addEventListener('click', () => {
  openModal(document.querySelector('#add-modal'));
}));

const addItemForm = document.querySelector('[data-add-item-form]');
const addItemNotification = document.querySelector('[data-add-item-notification]');
const inventoryUpdates = 'BroadcastChannel' in window ? new BroadcastChannel('pantrypilot-inventory') : null;

async function refreshInventory() {
  const inventoryPanel = document.querySelector('.inventory-panel');
  if (!inventoryPanel) return;
  const response = await fetch(`${window.location.pathname}${window.location.search}`, {
    headers: { 'X-Inventory-Refresh': '1' },
  });
  if (!response.ok) return;
  const page = new DOMParser().parseFromString(await response.text(), 'text/html');
  const updatedPanel = page.querySelector('.inventory-panel');
  if (updatedPanel) inventoryPanel.replaceWith(updatedPanel);
}

inventoryUpdates?.addEventListener('message', refreshInventory);

addItemForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submitButton = addItemForm.querySelector('[type="submit"]');
  submitButton.disabled = true;
  addItemNotification.hidden = true;

  try {
    const response = await fetch(addItemForm.action, {
      method: 'POST',
      body: new FormData(addItemForm),
      headers: { Accept: 'application/json' },
    });
    const result = await response.json();
    addItemNotification.textContent = result.message;
    addItemNotification.className = `modal-notification ${response.ok ? 'success' : 'error'}`;
    addItemNotification.hidden = false;
    if (response.ok) {
      addItemForm.querySelector('[name="name"]').value = '';
      refreshInventory();
      inventoryUpdates?.postMessage('item-added');
      try {
        localStorage.setItem('pantrypilot-inventory-updated', String(Date.now()));
      } catch (_storageError) {
        // BroadcastChannel still keeps supported tabs synchronized.
      }
    }
  } catch (_error) {
    addItemNotification.textContent = 'The item could not be added. Please try again.';
    addItemNotification.className = 'modal-notification error';
    addItemNotification.hidden = false;
  } finally {
    submitButton.disabled = false;
    addItemForm.querySelector('[name="name"]').focus();
  }
});

document.querySelector('[data-done-adding]')?.addEventListener('click', () => {
  closeModal(document.querySelector('#add-modal'));
});

window.addEventListener('storage', (event) => {
  if (event.key === 'pantrypilot-inventory-updated') refreshInventory();
});

document.querySelectorAll('[data-open-store-modal]').forEach((button) => button.addEventListener('click', () => {
  openModal(document.querySelector('#store-modal'));
}));

document.querySelectorAll('[data-open-category-modal]').forEach((button) => button.addEventListener('click', () => {
  openModal(document.querySelector('#category-modal'));
}));

document.querySelectorAll('[data-edit-category]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#edit-category-modal');
  modal.querySelector('form').action = button.dataset.action;
  modal.querySelector('[name="name"]').value = button.dataset.name;
  modal.querySelector('[name="color"]').value = button.dataset.color;
  modal.querySelector('output').value = button.dataset.color;
  openModal(modal);
}));

document.querySelectorAll('[data-delete-category]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#delete-category-modal');
  modal.querySelector('form').action = button.dataset.action;
  modal.querySelector('[data-delete-category-name]').textContent = button.dataset.name;
  openModal(modal);
}));

document.querySelectorAll('[data-edit-store]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#edit-store-modal');
  const form = modal.querySelector('form');
  const nameInput = modal.querySelector('[name="name"]');
  const colorInput = modal.querySelector('[name="color"]');
  form.action = button.dataset.action;
  nameInput.value = button.dataset.name;
  colorInput.value = button.dataset.color;
  modal.querySelector('output').value = button.dataset.color;
  openModal(modal);
}));

document.querySelectorAll('[data-delete-store]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#delete-store-modal');
  modal.querySelector('form').action = button.dataset.action;
  modal.querySelector('[data-delete-store-name]').textContent = button.dataset.name;
  openModal(modal);
}));

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-edit-item]');
  if (!button) return;
  const modal = document.querySelector('#edit-item-modal');
  const form = modal.querySelector('form');
  form.action = button.dataset.action;
  form.querySelector('[name="name"]').value = button.dataset.name;
  form.querySelector('[name="store_id"]').value = button.dataset.storeId;
  form.querySelector('[name="category_id"]').value = button.dataset.categoryId;
  form.querySelector('[name="quantity"]').value = button.dataset.quantity;
  form.querySelector('[name="item_minimum"]').value = button.dataset.itemMinimum;
  form.querySelector('[name="is_active"][type="checkbox"]').checked = button.dataset.isActive === '1';
  form.querySelector('[name="return_to"]').value = button.dataset.returnTo;
  form.querySelector('[name="return_query"]').value = button.dataset.returnQuery;
  openModal(modal);
});

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-delete-item]');
  if (!button) return;
  const modal = document.querySelector('#delete-item-modal');
  const form = modal.querySelector('form');
  form.action = button.dataset.action;
  form.querySelector('[name="return_to"]').value = button.dataset.returnTo;
  form.querySelector('[name="return_query"]').value = button.dataset.returnQuery;
  modal.querySelector('[data-delete-item-name]').textContent = button.dataset.name;
  openModal(modal);
});

document.querySelectorAll('.modal').forEach((modal) => {
  modal.querySelectorAll('.modal-close, [data-close-modal]').forEach((button) => {
    button.addEventListener('click', () => closeModal(modal));
  });
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeModal(modal);
  });
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') document.querySelectorAll('.modal.open').forEach(closeModal);
});

document.querySelectorAll('input[type="color"]').forEach((colorInput) => {
  colorInput.addEventListener('input', () => {
    colorInput.closest('.color-field').querySelector('output').value = colorInput.value;
  });
});

const databaseFile = document.querySelector('[data-database-file]');
const dropZone = document.querySelector('[data-drop-zone]');
const importButton = document.querySelector('[data-import-button]');
const fileName = document.querySelector('[data-file-name]');

function updateImportFile() {
  const file = databaseFile?.files[0];
  if (fileName) fileName.textContent = file ? file.name : 'SQLite .db files only';
  if (importButton) importButton.disabled = !file;
}

databaseFile?.addEventListener('change', updateImportFile);
['dragenter', 'dragover'].forEach((eventName) => dropZone?.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach((eventName) => dropZone?.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove('dragging');
}));
dropZone?.addEventListener('drop', (event) => {
  if (!event.dataTransfer.files.length) return;
  databaseFile.files = event.dataTransfer.files;
  updateImportFile();
});
