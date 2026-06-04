// Drives the declarative printer picker markup: populates the <select> with
// installed printers, auto-fills the read-only port, and runs the manual-add panel.
window.App = window.App || {};
(function (App) {
  const S = () => App.state;
  const { el } = App.dom;
  const NAME_KEY = 'usb_name';
  const PORT_KEY = 'usb_port';

  let select = null;
  let portInput = null;

  function setPort(value) {
    if (portInput) portInput.value = value;
    S().setField('PRINTER', PORT_KEY, value);
  }

  async function populate(selectName) {
    let printers = [];
    try {
      printers = await App.bridge.call('list_printers');
    } catch (e) {
      printers = [];
    }
    const current = selectName != null ? selectName : (S().getField('PRINTER', NAME_KEY) || '');
    const names = printers.map((p) => p.name);
    App.dom.clear(select);
    // Keep a manual / saved name selectable even if it's not an installed queue.
    if (current && names.indexOf(current) === -1) {
      select.append(el('option', null, { value: current, textContent: current + ' (not installed)' }));
    }
    printers.forEach((p) => select.append(el('option', null, { value: p.name, textContent: p.name })));
    select.value = current;
    if (selectName != null) S().setField('PRINTER', NAME_KEY, selectName);
  }

  function init() {
    select = document.getElementById('printer-select');
    portInput = document.querySelector('[data-key="usb_port"]');
    if (!select) return;

    select.addEventListener('change', async () => {
      const name = select.value;
      S().setField('PRINTER', NAME_KEY, name);
      let port = '';
      try {
        port = await App.bridge.call('get_printer_port', name);
      } catch (e) {
        port = '';
      }
      if (port) setPort(port);
    });

    document.querySelector('[data-act="printer-refresh"]').addEventListener('click', () => populate());

    const panel = document.getElementById('manual-panel');
    const addBtn = document.querySelector('[data-act="printer-add"]');
    const closePanel = () => { panel.setAttribute('hidden', ''); addBtn.textContent = '+ Add manually'; };
    addBtn.addEventListener('click', () => {
      if (panel.hasAttribute('hidden')) { panel.removeAttribute('hidden'); addBtn.textContent = '− Cancel manual add'; }
      else closePanel();
    });
    document.getElementById('manual-cancel').addEventListener('click', closePanel);

    const nameIn = document.getElementById('manual-name');
    const portIn = document.getElementById('manual-port');
    const status = document.getElementById('manual-status');
    document.getElementById('manual-test').addEventListener('click', async () => {
      const name = nameIn.value.trim();
      const port = portIn.value.trim();
      if (!name) {
        status.textContent = 'Enter a printer name.';
        status.style.color = 'var(--danger)';
        return;
      }
      let res;
      try {
        res = await App.bridge.call('test_connection', name, port);
      } catch (e) {
        res = { ok: false, message: String(e) };
      }
      if (!res || !res.ok) {
        status.textContent = '✗ ' + (res && res.message || 'Connection failed');
        status.style.color = 'var(--danger)';
        return;
      }
      S().setField('PRINTER', NAME_KEY, name);
      let resolved = port;
      if (!resolved) {
        try { resolved = await App.bridge.call('get_printer_port', name); } catch (e) { resolved = ''; }
      }
      if (resolved) setPort(resolved);
      await populate(name);
      status.textContent = '✓ ' + res.message + ' Printer set.';
      status.style.color = 'var(--success)';
      closePanel();
    });

    populate();
  }

  App.printer = { init, reload: () => populate() };
})(window.App);
