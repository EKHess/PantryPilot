const sidebar = document.querySelector('#sidebar');
const toggle = document.querySelector('.menu-toggle');

toggle?.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  toggle.setAttribute('aria-expanded', String(open));
});

function openModal(modal) {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  modal.querySelector('input, select, button')?.focus();
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

const colorInput = document.querySelector('#store-color');
colorInput?.addEventListener('input', () => {
  document.querySelector('output[for="store-color"]').value = colorInput.value;
});
