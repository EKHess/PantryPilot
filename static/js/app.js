const sidebar = document.querySelector('#sidebar');
const toggle = document.querySelector('.menu-toggle');
const modal = document.querySelector('#add-modal');

toggle?.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  toggle.setAttribute('aria-expanded', String(open));
});

document.querySelectorAll('[data-open-modal]').forEach((button) => button.addEventListener('click', () => {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  modal.querySelector('input').focus();
}));

function closeModal() { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); }
document.querySelectorAll('.modal-close, [data-close-modal]').forEach((button) => button.addEventListener('click', closeModal));
modal.addEventListener('click', (event) => { if (event.target === modal) closeModal(); });
