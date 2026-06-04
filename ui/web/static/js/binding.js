// Binds the declarative HTML form controls (data-key / data-image / data-filepicker
// / data-act) to the config state. No widgets are built in JS here — the markup
// lives in index.html; this is just the wiring.
window.App = window.App || {};
(function (App) {
  const S = () => App.state;
  const { el, icon } = App.dom;

  const sectionOf = (node) => node.closest('[data-section]').dataset.section;

  function coerce(inp) {
    if (inp.type === 'checkbox') return inp.checked;
    if (inp.dataset.type === 'int' || inp.type === 'range') {
      const n = parseInt(inp.value, 10);
      return isNaN(n) ? 0 : n;
    }
    return inp.value;
  }

  function updateReadout(inp) {
    if (inp.type !== 'range') return;
    const out = inp.closest('.slider-row') && inp.closest('.slider-row').querySelector('.slider-value');
    if (out) out.textContent = inp.value + (inp.dataset.unit || '');
  }

  function loadInput(inp) {
    const val = S().getField(sectionOf(inp), inp.dataset.key);
    if (inp.type === 'checkbox') inp.checked = !!val;
    else inp.value = val == null ? '' : val;
    updateReadout(inp);
  }

  function bindInput(inp) {
    loadInput(inp);
    const ev = inp.tagName === 'SELECT' || inp.type === 'checkbox' ? 'change' : 'input';
    inp.addEventListener(ev, () => {
      S().setField(sectionOf(inp), inp.dataset.key, coerce(inp));
      updateReadout(inp);
    });
  }

  function loadSegmented(seg) {
    const cur = S().getField(sectionOf(seg), seg.dataset.key);
    seg.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.value === cur));
  }

  function bindSegmented(seg) {
    loadSegmented(seg);
    seg.querySelectorAll('button').forEach((b) => {
      b.addEventListener('click', () => {
        S().setField(sectionOf(seg), seg.dataset.key, b.dataset.value);
        seg.querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
      });
    });
  }

  function bindImage(field) {
    const section = sectionOf(field);
    const key = field.dataset.image;
    const thumb = field.querySelector('.image-thumb');
    let token = 0;
    async function refresh() {
      const p = (S().getField(section, key) || '').trim();
      thumb.textContent = '';
      thumb.classList.toggle('empty', !p);
      if (!p) { thumb.textContent = 'No image'; return; }
      thumb.textContent = '…';
      const my = ++token;
      const url = await App.bridge.call('image_thumb', p);
      if (my !== token) return;
      thumb.textContent = '';
      if (url) { thumb.classList.remove('empty'); thumb.append(el('img', null, { src: url })); }
      else { thumb.classList.add('empty'); thumb.textContent = p.split(/[\\/]/).pop(); }
    }
    async function browse() {
      const picked = await App.bridge.call('pick_file', section + '|' + key);
      if (picked) { S().setField(section, key, picked); refresh(); }
    }
    // The thumbnail itself is the browse control (click or Enter/Space).
    thumb.setAttribute('role', 'button');
    thumb.tabIndex = 0;
    thumb.addEventListener('click', browse);
    thumb.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); browse(); }
    });
    const browseBtn = field.querySelector('[data-act="browse"]');
    if (browseBtn) browseBtn.addEventListener('click', browse);
    const clearBtn = field.querySelector('[data-act="clear"]');
    if (clearBtn) clearBtn.addEventListener('click', () => { S().setField(section, key, ''); refresh(); });
    field._refresh = refresh;
    refresh();
  }

  function bindFilePicker(row) {
    const section = sectionOf(row);
    const key = row.dataset.filepicker;
    const input = row.querySelector('input');
    row.querySelector('[data-act="browse"]').addEventListener('click', async () => {
      const picked = await App.bridge.call('pick_file', section + '|' + key);
      if (picked) { input.value = picked; input.title = picked; S().setField(section, key, picked); }
    });
  }

  // Re-sync every control from config (after Cancel/Reset).
  function reload() {
    document.querySelectorAll('.form-section [data-key]:not(#printer-select)').forEach(loadInput);
    document.querySelectorAll('.form-section .segmented[data-key]').forEach(loadSegmented);
    document.querySelectorAll('.form-section .image-field').forEach((f) => f._refresh && f._refresh());
    if (App.printer && App.printer.reload) App.printer.reload();
  }

  function init() {
    document.querySelectorAll('[data-icon]').forEach((b) => b.prepend(icon(b.dataset.icon)));
    // The printer <select> is owned by printer.js (runtime options + port sync).
    document.querySelectorAll('.form-section [data-key]:not(#printer-select)').forEach(bindInput);
    document.querySelectorAll('.form-section .segmented[data-key]').forEach(bindSegmented);
    document.querySelectorAll('.form-section .image-field[data-image]').forEach(bindImage);
    document.querySelectorAll('.form-section .file-row[data-filepicker]').forEach(bindFilePicker);

    const actions = { 'open-drivers': () => App.bridge.call('open_drivers') };
    document.querySelectorAll('[data-act]').forEach((b) => {
      const fn = actions[b.dataset.act];
      if (fn) b.addEventListener('click', fn);
    });
  }

  App.binding = { init, reload };
})(window.App);
