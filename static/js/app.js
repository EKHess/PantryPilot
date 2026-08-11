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

document.querySelectorAll('[data-edit-item]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#edit-item-modal');
  const form = modal.querySelector('form');
  form.action = button.dataset.action;
  form.querySelector('[name="name"]').value = button.dataset.name;
  form.querySelector('[name="store_id"]').value = button.dataset.storeId;
  form.querySelector('[name="category_id"]').value = button.dataset.categoryId;
  form.querySelector('[name="quantity"]').value = button.dataset.quantity;
  form.querySelector('[name="return_to"]').value = button.dataset.returnTo;
  openModal(modal);
}));

document.querySelectorAll('[data-delete-item]').forEach((button) => button.addEventListener('click', () => {
  const modal = document.querySelector('#delete-item-modal');
  const form = modal.querySelector('form');
  form.action = button.dataset.action;
  form.querySelector('[name="return_to"]').value = button.dataset.returnTo;
  modal.querySelector('[data-delete-item-name]').textContent = button.dataset.name;
  openModal(modal);
}));

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
