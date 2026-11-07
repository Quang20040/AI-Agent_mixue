/* Lean UI runtime (no animation library): page search dialog (Ctrl+K) and the shared stylesheet <link>. */
(() => {
  const d = document;
  for (const href of (window.__mixueCss || [])) {
    if (!d.head.querySelector(`link[data-mixue-css="${href}"]`)) {
      d.head.querySelectorAll('link[data-mixue-css]').forEach(old => old.remove());
      const link = d.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.dataset.mixueCss = href;
      d.head.appendChild(link);
    }
  }
  if (window.mixueUi?.version === 1) return;
  window.mixueMotion?.destroy?.();
  const normalize = value => value.toLocaleLowerCase('vi').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd');
  const openSearch = () => {
    const dialog = d.querySelector('.mx-command');
    if (!dialog || dialog.open) return;
    dialog.showModal();
    dialog.querySelector('input')?.focus();
  };
  d.addEventListener('click', event => {
    if (event.target.closest('[data-command-open]')) openSearch();
    if (event.target.closest('[data-command-close]')) event.target.closest('dialog')?.close();
    const action = event.target.closest('[data-command-page]');
    if (!action) return;
    const target = action.dataset.commandPage.trim();
    const option = [...d.querySelectorAll('.st-key-main_navigation label')].find(label => label.textContent.trim() === target);
    if (option) { d.querySelector('.mx-command[open]')?.close(); option.click(); }
  });
  d.addEventListener('input', event => {
    if (!event.target.matches('.mx-command input')) return;
    const dialog = event.target.closest('dialog');
    const query = normalize(event.target.value);
    let visible = 0;
    dialog.querySelectorAll('[data-command-page]').forEach(button => {
      button.hidden = !normalize(button.dataset.commandPage).includes(query);
      if (!button.hidden) visible++;
    });
    dialog.querySelector('.mx-command-empty').hidden = Boolean(visible);
  });
  d.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && d.querySelector('.mx-command')) { event.preventDefault(); openSearch(); }
    if (event.key === 'Enter' && event.target.matches('.mx-command input')) { event.preventDefault(); event.target.closest('dialog').querySelector('[data-command-page]:not([hidden])')?.click(); }
  });
  window.mixueUi = {version: 1};
})();
