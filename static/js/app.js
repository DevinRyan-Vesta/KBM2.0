/* VKeys app shell: theme, drawer, search, toasts, confirm sheet, table sort.
   Page-specific config arrives via window.VKEYS (set inline in base.html). */
(function () {
  'use strict';

  const CFG = window.VKEYS || {};
  const body = document.body;
  const html = document.documentElement;

  function icon(name, size) {
    const i = document.createElement('i');
    i.setAttribute('data-lucide', name);
    if (size) { i.style.width = size + 'px'; i.style.height = size + 'px'; }
    return i;
  }
  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ------------------------------------------------------------------ theme
  // <html data-theme> is the source of truth (set before first paint in
  // base.html). body.light / body.dark are kept for page-level overrides.
  function currentTheme() { return html.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; }
  function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    body.classList.toggle('dark', theme === 'dark');
    body.classList.toggle('light', theme !== 'dark');
    try { localStorage.setItem('vkeys-theme', theme); } catch (e) { /* private mode */ }
    document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
      btn.innerHTML = '';
      btn.appendChild(icon(theme === 'dark' ? 'sun' : 'moon'));
      btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      btn.setAttribute('data-tooltip', theme === 'dark' ? 'Light mode' : 'Dark mode');
    });
    refreshIcons();
    window.dispatchEvent(new CustomEvent('vkeys:theme', { detail: { theme } }));
  }
  window.applyTheme = applyTheme;
  applyTheme(currentTheme());
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    e.preventDefault();
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  });

  // ----------------------------------------------------------------- drawer
  const layout = document.querySelector('.layout');
  function setDrawer(open) {
    if (!layout) return;
    layout.classList.toggle('sidebar-open', open);
    document.querySelectorAll('[data-sidebar-toggle]').forEach((b) => b.setAttribute('aria-expanded', String(open)));
  }
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-sidebar-toggle]')) { e.preventDefault(); setDrawer(!layout.classList.contains('sidebar-open')); return; }
    if (e.target.closest('.drawer-backdrop')) { setDrawer(false); return; }
    if (e.target.closest('.sidebar .nav-links a')) { setDrawer(false); }
  });

  // ------------------------------------------------------------------ toast
  // toast('Saved'); toast('Saved', { type: 'success' }); toast(msg, { duration: 0 })
  // undoToast('Deleted KA001', () => restore(), 8)
  const TOAST_ICONS = { success: 'circle-check', error: 'circle-x', warning: 'triangle-alert', info: 'info' };
  function toastHost() { return document.getElementById('toast-host'); }
  function dismiss(el) {
    if (!el || el.classList.contains('is-dismissing')) return;
    el.classList.add('is-dismissing');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  }
  window.toast = function (message, opts) {
    opts = opts || {};
    const type = opts.type || 'info';
    const duration = opts.duration === 0 ? 0 : (opts.duration || 4500);
    const root = toastHost();
    if (!root) return null;
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    const ic = document.createElement('span'); ic.className = 'toast-icon'; ic.appendChild(icon(TOAST_ICONS[type] || 'info'));
    const msg = document.createElement('span'); msg.className = 'toast-msg'; msg.textContent = message;
    el.appendChild(ic); el.appendChild(msg);
    if (typeof opts.onUndo === 'function') {
      const undo = document.createElement('button'); undo.type = 'button'; undo.className = 'toast-undo';
      let left = Math.ceil(duration / 1000);
      undo.textContent = 'Undo' + (left ? ' (' + left + ')' : '');
      const tick = setInterval(() => { left -= 1; if (left > 0) undo.textContent = 'Undo (' + left + ')'; else clearInterval(tick); }, 1000);
      undo.addEventListener('click', () => { clearInterval(tick); opts.onUndo(); dismiss(el); });
      el.appendChild(undo);
    }
    const close = document.createElement('button'); close.type = 'button'; close.className = 'icon-btn toast-close'; close.setAttribute('aria-label', 'Dismiss');
    close.appendChild(icon('x')); close.addEventListener('click', () => dismiss(el));
    el.appendChild(close);
    root.appendChild(el);
    refreshIcons(el);
    if (duration > 0) setTimeout(() => dismiss(el), duration);
    return el;
  };
  window.undoToast = function (message, onUndo, seconds) {
    return window.toast(message, { type: 'info', duration: (seconds || 8) * 1000, onUndo });
  };

  const FLASH_ICONS = { success: 'circle-check', error: 'circle-x', warning: 'triangle-alert', info: 'info', message: 'info' };
  function decorateFlashes() {
    document.querySelectorAll('.flash-container .flash').forEach((flash) => {
      const cat = ['success', 'info', 'warning', 'message'].find((c) => flash.classList.contains(c)) || 'error';
      if (!flash.querySelector('svg, i[data-lucide]')) flash.prepend(icon(FLASH_ICONS[cat]));
      flash.title = 'Click to dismiss';
      flash.addEventListener('click', () => dismiss(flash));
      setTimeout(() => dismiss(flash), cat === 'error' ? 12000 : 6000);
    });
  }

  // ---------------------------------------------------------- confirm sheet
  // const r = await confirmAction({ title, body, effect, confirmLabel, cancelLabel, danger,
  //                                 input: { label, placeholder, type: 'text'|'select', options, required, value } });
  // Resolves to { value } (value '' for plain confirms) or null when cancelled.
  let confirmRoot = null;
  function ensureConfirmRoot() {
    if (confirmRoot) return confirmRoot;
    confirmRoot = document.createElement('div');
    confirmRoot.className = 'confirm-root';
    confirmRoot.innerHTML =
      '<div class="modal-backdrop" data-confirm-cancel></div>' +
      '<div class="confirm-sheet" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">' +
        '<div class="confirm-head"><span class="confirm-icon"></span><h2 id="confirm-title"></h2>' +
        '<button type="button" class="icon-btn" data-confirm-cancel aria-label="Close"></button></div>' +
        '<p class="confirm-body"></p><div class="confirm-effect"></div><div class="confirm-input"></div>' +
        '<div class="confirm-actions"><button type="button" class="btn" data-confirm-cancel></button>' +
        '<button type="button" class="btn" data-confirm-ok></button></div></div>';
    document.body.appendChild(confirmRoot);
    confirmRoot.querySelector('.confirm-head .icon-btn').appendChild(icon('x'));
    return confirmRoot;
  }
  window.confirmAction = function (opts) {
    opts = opts || {};
    const root = ensureConfirmRoot();
    const sheet = root.querySelector('.confirm-sheet');
    const head = root.querySelector('.confirm-icon');
    const title = root.querySelector('#confirm-title');
    const bodyEl = root.querySelector('.confirm-body');
    const effect = root.querySelector('.confirm-effect');
    const inputWrap = root.querySelector('.confirm-input');
    const okBtn = root.querySelector('[data-confirm-ok]');
    const cancelBtn = root.querySelector('.confirm-actions [data-confirm-cancel]');
    const danger = !!opts.danger;

    sheet.classList.toggle('danger', danger);
    head.innerHTML = ''; if (danger) head.appendChild(icon('triangle-alert'));
    title.textContent = opts.title || (danger ? 'Are you sure?' : 'Please confirm');
    bodyEl.textContent = opts.body || '';
    bodyEl.style.display = opts.body ? '' : 'none';
    if (opts.effect) { effect.innerHTML = '<span class="caption">What this does</span>' + escapeHtml(opts.effect); effect.style.display = ''; }
    else { effect.innerHTML = ''; effect.style.display = 'none'; }
    inputWrap.innerHTML = '';
    let field = null;
    if (opts.input) {
      const inp = opts.input;
      const lab = document.createElement('label'); lab.textContent = inp.label || ''; lab.htmlFor = 'confirm-field';
      if (inp.type === 'select') {
        field = document.createElement('select');
        (inp.options || []).forEach((o) => {
          const opt = document.createElement('option');
          if (typeof o === 'string') { opt.value = o; opt.textContent = o; } else { opt.value = o.value; opt.textContent = o.label; }
          field.appendChild(opt);
        });
      } else {
        field = document.createElement('input'); field.type = inp.type || 'text'; field.placeholder = inp.placeholder || '';
      }
      field.id = 'confirm-field';
      if (inp.value != null) field.value = inp.value;
      if (inp.label) inputWrap.appendChild(lab);
      inputWrap.appendChild(field);
    }
    okBtn.textContent = opts.confirmLabel || (danger ? 'Delete' : 'Confirm');
    okBtn.className = 'btn ' + (danger ? 'danger filled' : 'primary');
    cancelBtn.textContent = opts.cancelLabel || 'Cancel';
    refreshIcons(root);

    const previouslyFocused = document.activeElement;
    root.classList.add('show');
    body.classList.add('modal-open');
    (field || okBtn).focus();
    if (field && field.select) field.select();

    return new Promise((resolve) => {
      function done(result) {
        root.classList.remove('show');
        body.classList.remove('modal-open');
        root.removeEventListener('click', onClick);
        document.removeEventListener('keydown', onKey, true);
        if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
        resolve(result);
      }
      function ok() {
        const value = field ? field.value : '';
        if (field && opts.input && opts.input.required && !String(value).trim()) { field.focus(); return; }
        done({ value });
      }
      function onClick(e) {
        if (e.target.closest('[data-confirm-ok]')) ok();
        else if (e.target.closest('[data-confirm-cancel]')) done(null);
      }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); done(null); }
        else if (e.key === 'Enter' && (!field || field.tagName !== 'TEXTAREA')) { e.preventDefault(); ok(); }
        else if (e.key === 'Tab') {
          const f = Array.from(sheet.querySelectorAll('button, input, select')).filter((el) => !el.disabled);
          if (!f.length) return;
          const first = f[0], last = f[f.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      }
      root.addEventListener('click', onClick);
      document.addEventListener('keydown', onKey, true);
    });
  };

  // Declarative guard: <form data-confirm="Delete KA001?" data-confirm-danger data-confirm-title="…">
  // or <a|button data-confirm="…">. The submit/click only proceeds after the sheet is confirmed.
  function guardOptions(el) {
    return {
      title: el.getAttribute('data-confirm-title') || undefined,
      body: el.getAttribute('data-confirm') || '',
      effect: el.getAttribute('data-confirm-effect') || undefined,
      confirmLabel: el.getAttribute('data-confirm-label') || undefined,
      danger: el.hasAttribute('data-confirm-danger') || /\b(delete|remove|revoke|cannot be undone|permanently)\b/i.test(el.getAttribute('data-confirm') || ''),
    };
  }
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-confirm') || form.dataset.confirmed === '1') return;
    e.preventDefault();
    window.confirmAction(guardOptions(form)).then((r) => {
      if (!r) return;
      form.dataset.confirmed = '1';
      if (typeof form.requestSubmit === 'function') form.requestSubmit(); else form.submit();
      setTimeout(() => { delete form.dataset.confirmed; }, 2000);
    });
  }, true);
  document.addEventListener('click', (e) => {
    const el = e.target.closest('a[data-confirm], button[data-confirm]:not([type="submit"])');
    if (!el || el.dataset.confirmed === '1') return;
    e.preventDefault();
    window.confirmAction(guardOptions(el)).then((r) => {
      if (!r) return;
      el.dataset.confirmed = '1';
      el.click();
      setTimeout(() => { delete el.dataset.confirmed; }, 2000);
    });
  }, true);

  // ----------------------------------------------------------- export menu
  // Shared "Export ▾" menu. Pages may define their own showExportMenu with the
  // same signature; those definitions win because page scripts load later.
  let exportType = null;
  function exportMenu() {
    let menu = document.getElementById('export-menu');
    if (!menu) {
      menu = document.createElement('div');
      menu.id = 'export-menu'; menu.className = 'dropdown-menu'; menu.style.display = 'none';
      [['csv', 'CSV', 'file-text'], ['excel', 'Excel', 'file-spreadsheet'], ['pdf', 'PDF', 'file-down']].forEach(([fmt, label, ic]) => {
        const a = document.createElement('a'); a.href = '#'; a.dataset.format = fmt;
        a.appendChild(icon(ic)); a.appendChild(document.createTextNode('Export as ' + label));
        a.addEventListener('click', (e) => window.exportData(e, fmt));
        menu.appendChild(a);
      });
      document.body.appendChild(menu);
      refreshIcons(menu);
    }
    return menu;
  }
  function closeExportMenu(event) {
    const menu = document.getElementById('export-menu');
    if (!menu) return;
    if (event && menu.contains(event.target)) return;
    menu.style.display = 'none';
    document.removeEventListener('click', closeExportMenu);
  }
  window.showExportMenu = function (event, itemType, formats) {
    event.preventDefault();
    const menu = exportMenu();
    const rect = event.currentTarget ? event.currentTarget.getBoundingClientRect() : event.target.getBoundingClientRect();
    menu.querySelectorAll('a[data-format]').forEach((a) => { a.style.display = (!formats || formats.includes(a.dataset.format)) ? '' : 'none'; });
    menu.style.position = 'fixed';
    menu.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 220)) + 'px';
    menu.style.top = (rect.bottom + 6) + 'px';
    menu.style.display = 'block';
    exportType = itemType;
    setTimeout(() => document.addEventListener('click', closeExportMenu), 0);
  };
  window.closeExportMenu = closeExportMenu;
  window.exportData = function (event, format) {
    event.preventDefault();
    if (!exportType) return;
    window.location.href = '/exports/items/' + exportType + '?format=' + format;
    closeExportMenu();
  };

  // ------------------------------------------------------------ table sort
  // <table data-sortable>: click a header to sort rows client-side. Cells
  // with data-sort use that value; numbers and dates sort naturally.
  function cellValue(tr, idx) {
    const td = tr.children[idx];
    if (!td) return '';
    const raw = td.hasAttribute('data-sort') ? td.getAttribute('data-sort') : td.textContent;
    return raw.trim();
  }
  function compare(a, b) {
    const na = parseFloat(a.replace(/[,$%]/g, '')), nb = parseFloat(b.replace(/[,$%]/g, ''));
    if (!isNaN(na) && !isNaN(nb) && /^[\s\d.,$%-]+$/.test(a) && /^[\s\d.,$%-]+$/.test(b)) return na - nb;
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
  }
  function initSortable(table) {
    const ths = Array.from(table.querySelectorAll('thead th'));
    ths.forEach((th, idx) => {
      if (th.classList.contains('no-sort') || th.classList.contains('select-col') || th.classList.contains('actions-col')) return;
      if (!th.textContent.trim()) return;
      if (!th.querySelector('.sort-icon')) {
        const s = document.createElement('span'); s.className = 'sort-icon'; s.appendChild(icon('arrow-up-down'));
        th.appendChild(s);
      }
      th.setAttribute('tabindex', '0');
      const run = () => {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        ths.forEach((o) => { o.removeAttribute('aria-sort'); const si = o.querySelector('.sort-icon'); if (si) { si.innerHTML = ''; si.appendChild(icon('arrow-up-down')); } });
        th.setAttribute('aria-sort', dir);
        const si = th.querySelector('.sort-icon'); si.innerHTML = ''; si.appendChild(icon(dir === 'ascending' ? 'arrow-up' : 'arrow-down'));
        const rows = Array.from(tbody.rows).filter((r) => !r.classList.contains('no-sort'));
        rows.sort((a, b) => { const c = compare(cellValue(a, idx), cellValue(b, idx)); return dir === 'ascending' ? c : -c; });
        rows.forEach((r) => tbody.appendChild(r));
        refreshIcons(table);
      };
      th.addEventListener('click', (e) => { if (e.target.closest('input, button, a')) return; run(); });
      th.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); run(); } });
    });
    refreshIcons(table);
  }

  // -------------------------------------------------------------- row menus
  // A table row shows its first action inline and folds the rest into a
  // "More" menu (td .row-buttons with three or more actions).
  let openRowMenu = null;
  function closeRowMenu() {
    if (!openRowMenu) return;
    openRowMenu.menu.style.display = 'none';
    openRowMenu.btn.setAttribute('aria-expanded', 'false');
    openRowMenu = null;
  }
  function initRowMenus() {
    document.querySelectorAll('td .row-buttons').forEach((group) => {
      if (group.dataset.rowMenu === '1') return;
      const children = Array.from(group.children).filter((c) => c.tagName !== 'SCRIPT');
      if (children.length < 3) return;
      group.dataset.rowMenu = '1';
      const menu = document.createElement('div');
      menu.className = 'dropdown-menu row-menu';
      menu.style.display = 'none';
      menu.setAttribute('role', 'menu');
      children.slice(1).forEach((c) => menu.appendChild(c));
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn link small row-more';
      btn.setAttribute('aria-haspopup', 'menu');
      btn.setAttribute('aria-expanded', 'false');
      btn.appendChild(document.createTextNode('More'));
      btn.appendChild(icon('chevron-down'));
      group.appendChild(btn);
      document.body.appendChild(menu);
      btn.addEventListener('click', (e) => {
        e.preventDefault(); e.stopPropagation();
        if (openRowMenu && openRowMenu.menu === menu) { closeRowMenu(); return; }
        closeRowMenu();
        const r = btn.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.display = 'block';
        const w = menu.offsetWidth || 190, h = menu.offsetHeight || 200;
        menu.style.left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)) + 'px';
        menu.style.top = (r.bottom + h + 12 > window.innerHeight ? r.top - h - 6 : r.bottom + 6) + 'px';
        btn.setAttribute('aria-expanded', 'true');
        openRowMenu = { btn, menu };
        const first = menu.querySelector('button, a');
        if (first) first.focus();
      });
      menu.addEventListener('click', (e) => { if (e.target.closest('a, button')) setTimeout(closeRowMenu, 0); });
    });
    refreshIcons();
  }
  document.addEventListener('click', (e) => { if (openRowMenu && !openRowMenu.menu.contains(e.target)) closeRowMenu(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeRowMenu(); });
  window.addEventListener('scroll', closeRowMenu, true);

  // ---------------------------------------------------------- receipt modal
  let receiptId = null;
  window.showReceiptModal = function (id) {
    receiptId = id;
    const modal = document.getElementById('receipt-modal');
    if (!modal) return;
    modal.classList.add('show');
    body.classList.add('modal-open');
  };
  window.closeReceiptModal = function () {
    const modal = document.getElementById('receipt-modal');
    if (modal) modal.classList.remove('show');
    body.classList.remove('modal-open');
    if (window.history.replaceState) {
      const url = new URL(window.location);
      url.searchParams.delete('receipt_id');
      window.history.replaceState({}, '', url);
    }
  };
  window.printReceipt = function () {
    if (receiptId && CFG.receiptUrl) window.open(CFG.receiptUrl.replace('/0/', '/' + receiptId + '/'), '_blank');
    window.closeReceiptModal();
  };

  // --------------------------------------------------------- idle timeout
  // Sessions are sliding-window server side; mirror that here so the user
  // gets a heads-up toast before the cookie dies, then a clean logout.
  function initIdleTimeout() {
    const TIMEOUT_SEC = Number(CFG.sessionTimeout || 0);
    if (!CFG.authenticated || !TIMEOUT_SEC || TIMEOUT_SEC <= 0 || !CFG.logoutUrl) return;
    const TIMEOUT_MS = TIMEOUT_SEC * 1000;
    const WARN_BEFORE_MS = Math.min(5 * 60 * 1000, TIMEOUT_MS * 0.2);
    const WARN_AT_MS = Math.max(TIMEOUT_MS - WARN_BEFORE_MS, TIMEOUT_MS / 2);
    let lastActivity = Date.now();
    let warned = null;
    function recordActivity() { lastActivity = Date.now(); if (warned) { dismiss(warned); warned = null; } }
    ['mousedown', 'keydown', 'touchstart', 'scroll'].forEach((evt) => document.addEventListener(evt, recordActivity, { passive: true }));
    setInterval(() => {
      const idle = Date.now() - lastActivity;
      if (idle >= TIMEOUT_MS) { window.location.href = CFG.logoutUrl; return; }
      if (idle >= WARN_AT_MS && !warned) {
        const mins = Math.max(1, Math.ceil((TIMEOUT_MS - idle) / 60000));
        warned = window.toast('Logging out in ' + mins + ' min due to inactivity. Click anywhere to stay.', { type: 'warning', duration: 0 });
      }
    }, 30000);
  }

  // -------------------------------------------------------- global search
  function initGlobalSearch() {
    const form = document.getElementById('global-search');
    if (!form) return;
    const input = form.querySelector('.global-search-input');
    const dropdown = form.querySelector('.global-search-dropdown');
    const searchUrl = form.getAttribute('action');
    const suggestUrl = form.getAttribute('data-suggest-url') || '/search/suggest';
    const ICONS = { lockbox: 'lock', key: 'key-round', sign: 'signpost', item: 'package', property: 'building', contact: 'users', smartlock: 'lock-keyhole', receipt: 'receipt-text', user: 'user-round' };
    let debounceTimer = null, activeFetch = null, activeIndex = -1, currentResults = [];
    const cache = new Map();

    function open() { form.classList.add('is-open'); }
    function close() { form.classList.remove('is-open'); activeIndex = -1; }
    function render(results, query) {
      currentResults = results; activeIndex = -1;
      if (!query) { close(); return; }
      const full = searchUrl + '?q=' + encodeURIComponent(query);
      if (!results.length) {
        dropdown.innerHTML = '<div class="global-search-empty">No matches for "' + escapeHtml(query) + '"</div>' +
          '<a href="' + escapeHtml(full) + '" class="global-search-footer">Search anyway</a>';
        open(); return;
      }
      let htmlStr = '';
      results.forEach((r, i) => {
        htmlStr += '<a href="' + escapeHtml(r.url) + '" class="global-search-item" data-idx="' + i + '">' +
          '<span class="global-search-icon-cell"><i data-lucide="' + (ICONS[r.type] || 'search') + '"></i></span>' +
          '<span class="global-search-text"><span class="global-search-label">' + escapeHtml(r.label || '') +
          '<span class="global-search-type">' + escapeHtml(r.type_label || '') + '</span></span>' +
          (r.subtitle ? '<span class="global-search-subtitle">' + escapeHtml(r.subtitle) + '</span>' : '') + '</span></a>';
      });
      htmlStr += '<a href="' + escapeHtml(full) + '" class="global-search-footer">View all results for "' + escapeHtml(query) + '"</a>';
      dropdown.innerHTML = htmlStr;
      refreshIcons(dropdown);
      open();
    }
    function fetchSuggestions(query) {
      if (cache.has(query)) { render(cache.get(query), query); return; }
      if (activeFetch) activeFetch.abort();
      const controller = new AbortController(); activeFetch = controller;
      dropdown.innerHTML = '<div class="global-search-loading">Searching…</div>'; open();
      fetch(suggestUrl + '?q=' + encodeURIComponent(query), { signal: controller.signal })
        .then((r) => r.json())
        .then((data) => { const res = data.results || []; cache.set(query, res); render(res, data.query || query); })
        .catch((err) => { if (err.name !== 'AbortError') dropdown.innerHTML = '<div class="global-search-empty">Search failed.</div>'; });
    }
    input.addEventListener('input', () => {
      const q = input.value.trim();
      clearTimeout(debounceTimer);
      if (q.length < 2) { close(); return; }
      debounceTimer = setTimeout(() => fetchSuggestions(q), 150);
    });
    input.addEventListener('focus', () => { if (input.value.trim().length >= 2 && currentResults.length) open(); });
    input.addEventListener('keydown', (e) => {
      const items = dropdown.querySelectorAll('.global-search-item');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!form.classList.contains('is-open') || !items.length) return;
        e.preventDefault();
        activeIndex = e.key === 'ArrowDown' ? (activeIndex + 1) % items.length : (activeIndex - 1 + items.length) % items.length;
        items.forEach((el, i) => { el.classList.toggle('is-active', i === activeIndex); if (i === activeIndex) el.scrollIntoView({ block: 'nearest' }); });
      } else if (e.key === 'Enter') {
        if (activeIndex >= 0 && items[activeIndex]) { e.preventDefault(); window.location.href = items[activeIndex].getAttribute('href'); }
      } else if (e.key === 'Escape') { close(); input.blur(); }
    });
    document.addEventListener('click', (e) => { if (!form.contains(e.target)) close(); });

    // Ctrl/Cmd+K anywhere, or "/" outside a field, focuses search.
    document.addEventListener('keydown', (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || '')) || e.target.isContentEditable;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); input.focus(); input.select(); }
      else if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); input.focus(); }
    });
  }

  // ------------------------------------------------------------------ init
  function init() {
    decorateFlashes();
    document.querySelectorAll('table[data-sortable]').forEach(initSortable);
    initRowMenus();
    initGlobalSearch();
    initIdleTimeout();
    const rid = new URLSearchParams(window.location.search).get('receipt_id');
    if (rid) window.showReceiptModal(rid);
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const open = document.querySelector('.modal-root.show');
      if (open && open.id === 'receipt-modal') window.closeReceiptModal();
    });
    refreshIcons();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
