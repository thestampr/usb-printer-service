// Tiny DOM helpers shared across the UI modules.
window.App = window.App || {};
(function (App) {
  function el(tag, cls, props) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (props) Object.assign(node, props);
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  // Inline stroke icons (Lucide, 24px grid, currentColor) keyed by name.
  // https://lucide.dev — ISC licensed. Subpaths concatenated into one `d`.
  const ICONS = {
    check: 'M20 6 9 17l-5-5',
    undo: 'M9 14 4 9l5-5 M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11',
    reset: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8 M3 3v5h5',
    refresh: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16 M8 16H3v5',
    trash: 'M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6',
    folder: 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
    printer: 'M6 9V2h12v7 M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2 M6 14h12v8H6z',
    download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3',
    plus: 'M5 12h14 M12 5v14',
    save: 'M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7 M7 3v4a1 1 0 0 0 1 1h7',
    play: 'M6 4.5v15a1 1 0 0 0 1.5.87l12-7.5a1 1 0 0 0 0-1.74l-12-7.5A1 1 0 0 0 6 4.5z',
    stop: 'M7 6h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z',
  };

  function icon(name, cls) {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('class', 'icn' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', ICONS[name] || '');
    p.setAttribute('fill', 'none');
    p.setAttribute('stroke', 'currentColor');
    p.setAttribute('stroke-width', '2');
    p.setAttribute('stroke-linecap', 'round');
    p.setAttribute('stroke-linejoin', 'round');
    svg.append(p);
    return svg;
  }

  // Build a .btn with an optional leading icon.
  function btn(label, opts) {
    opts = opts || {};
    const b = el('button', 'btn' + (opts.cls ? ' ' + opts.cls : ''), { type: 'button' });
    if (opts.icon) b.append(icon(opts.icon));
    if (label) b.append(document.createTextNode(label));
    if (opts.title) b.title = opts.title;
    return b;
  }

  let toastTimer = null;
  function toast(message, kind) {
    let t = document.getElementById('toast');
    if (!t) {
      t = el('div', 'toast', { id: 'toast' });
      document.body.append(t);
    }
    t.className = 'toast' + (kind ? ' ' + kind : '');
    t.textContent = message;
    // reflow so the transition replays
    void t.offsetWidth;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
  }

  // Promise-based confirm dialog (avoids relying on window.confirm in webview).
  function confirm(message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      const overlay = el('div', 'modal-overlay');
      const box = el('div', 'modal-box');
      box.append(el('p', 'modal-msg', { textContent: message }));
      const row = el('div', 'modal-btns');
      const cancel = el('button', 'btn', { type: 'button', textContent: opts.cancelLabel || 'Cancel' });
      // Destructive confirmations use the outline danger style for the accept button.
      const ok = el('button', 'btn ' + (opts.danger ? 'danger' : 'primary'), { type: 'button', textContent: opts.okLabel || 'OK' });
      row.append(cancel, ok);
      box.append(row);
      overlay.append(box);
      document.body.append(overlay);
      const close = (val) => { overlay.remove(); resolve(val); };
      cancel.addEventListener('click', () => close(false));
      ok.addEventListener('click', () => close(true));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
    });
  }

  App.dom = { el, clear, toast, confirm, icon, btn };
})(window.App);
