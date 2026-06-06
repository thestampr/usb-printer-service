// Postman-style editor for the example (dummy) payload. Rows are cloned from the
// <template> elements in index.html (no widget building here beyond filling them).
window.App = window.App || {};
(function (App) {
  const S = () => App.state;
  const { el, clear } = App.dom;

  const tpl = (id) => document.getElementById(id).content.firstElementChild.cloneNode(true);

  function numStr(v) {
    if (v == null || v === '') return '';
    return String(v);
  }

  function cleanKV(obj) {
    const out = {};
    Object.entries(obj || {}).forEach(([k, v]) => {
      if (String(k).trim() !== '') out[String(k)] = String(v);
    });
    return out;
  }

  // Canonical form of a raw payload — what collect() yields from a clean render.
  // Used for baselines so merely viewing the tab never marks anything dirty.
  function normalize(data) {
    data = data || {};
    // Migrate the legacy "info-title" key to "info_title".
    if (data['info-title'] != null && data.info_title == null) data.info_title = data['info-title'];
    const payload = {};
    ['rfid', 'info_title'].forEach((k) => {
      const v = data[k];
      if (v != null && String(v).trim() !== '') payload[k] = String(v);
    });
    const hi = cleanKV(data.header_info);
    if (Object.keys(hi).length) payload.header_info = hi;

    const items = [];
    (data.items || []).forEach((it) => {
      const a = parseFloat(it.amount);
      const q = parseFloat(it.quantity);
      const name = String(it.name == null ? '' : it.name).trim();
      if (name && !isNaN(a) && !isNaN(q)) items.push({ name, amount: a, quantity: q });
    });
    payload.items = items;

    const fi = cleanKV(data.footer_info);
    if (Object.keys(fi).length) payload.footer_info = fi;

    const tx = {};
    ['received', 'change', 'discount', 'total'].forEach((k) => {
      const v = (data.transaction_info || {})[k];
      const n = parseFloat(v);
      if (v != null && String(v).trim() !== '' && !isNaN(n)) tx[k] = n;
    });
    if (Object.keys(tx).length) payload.transaction_info = tx;
    return payload;
  }

  // Per-row enable checkboxes coordinated with one bulk checkbox (both come from
  // the cloned templates; this just wires them).
  function makeToggleGroup(onChange) {
    const members = [];
    let bulkEl = null;

    function syncBulk() {
      if (!bulkEl) return;
      const total = members.length;
      const on = members.filter((m) => m.cb.checked).length;
      bulkEl.checked = total > 0 && on === total;
      bulkEl.indeterminate = on > 0 && on < total;
    }

    function rowToggle(cb, inputs) {
      const member = { cb, apply: () => inputs.forEach((i) => { i.disabled = !cb.checked; }) };
      cb.addEventListener('change', () => { member.apply(); syncBulk(); onChange(); });
      member.apply();
      members.push(member);
      syncBulk();
      return {
        isOn: () => cb.checked,
        remove: () => { const i = members.indexOf(member); if (i >= 0) members.splice(i, 1); syncBulk(); },
      };
    }

    function bulk(cb) {
      bulkEl = cb;
      cb.addEventListener('change', () => {
        const total = members.length;
        const on = members.filter((m) => m.cb.checked).length;
        const target = !(total > 0 && on === total);
        members.forEach((m) => { m.cb.checked = target; m.apply(); });
        syncBulk();
        onChange();
      });
      syncBulk();
    }

    return { rowToggle, bulk };
  }

  function buildCard(editor, title, hint) {
    const card = tpl('tpl-dummy-card');
    card.querySelector('.dummy-card-title').textContent = title;
    const h = card.querySelector('.dummy-card-hint');
    if (hint) h.textContent = hint; else h.remove();
    editor.append(card);
    return { card, bulkCb: card.querySelector('[data-bulk]') };
  }

  App.dummy = {
    _mounted: false,
    normalize,

    render() {
      const self = this;
      const editor = document.getElementById('dummy-editor');
      const data = S().dummy || {};
      clear(editor);
      const sync = () => S().setDummy(self.collect());
      this._sync = sync;

      // ---- Key/Value table (header_info / footer_info) ----------------
      function kvCard(title, hint, initial) {
        const group = makeToggleGroup(sync);
        const { card, bulkCb } = buildCard(editor, title, hint);
        group.bulk(bulkCb);
        const rows = [];
        card.append(tpl('tpl-kv-head'));
        const body = el('div', 'dummy-rows');
        card.append(body);

        function addRow(key, value, ghost) {
          const rf = tpl('tpl-kv-row');
          if (ghost) rf.classList.add('ghost-row');
          const cb = rf.querySelector('.dummy-check');
          const kIn = rf.querySelector('[data-cell="key"]');
          const vIn = rf.querySelector('[data-cell="value"]');
          kIn.value = key || ''; vIn.value = value || ''; cb.checked = true;
          const rm = rf.querySelector('.dummy-remove');
          body.append(rf);

          function makeReal() {
            const t = group.rowToggle(cb, [kIn, vIn]);
            const entry = { kIn, vIn, isOn: t.isOn };
            rows.push(entry);
            rm.addEventListener('click', () => {
              const i = rows.indexOf(entry); if (i >= 0) rows.splice(i, 1);
              t.remove(); rf.remove(); sync();
            });
            kIn.addEventListener('input', sync);
            vIn.addEventListener('input', sync);
          }
          if (ghost) {
            const promote = () => {
              if (kIn.value === '' && vIn.value === '') return;
              kIn.removeEventListener('input', promote);
              vIn.removeEventListener('input', promote);
              rf.classList.remove('ghost-row');
              makeReal(); sync();
              addRow('', '', true);
            };
            kIn.addEventListener('input', promote);
            vIn.addEventListener('input', promote);
          } else {
            makeReal();
          }
        }

        Object.entries(initial || {}).forEach(([k, v]) => addRow(String(k), String(v), false));
        addRow('', '', true);

        return () => {
          const out = {};
          rows.forEach((r) => { if (!r.isOn()) return; const k = r.kIn.value.trim(); if (k) out[k] = r.vIn.value; });
          return out;
        };
      }

      // ---- Items table ------------------------------------------------
      function itemsCard(initialItems) {
        const group = makeToggleGroup(sync);
        const { card, bulkCb } = buildCard(editor, 'Items', 'name · price/unit · quantity');
        group.bulk(bulkCb);
        const rows = [];
        card.append(tpl('tpl-item-head'));
        const body = el('div', 'dummy-rows');
        card.append(body);

        function addItem(name, amount, quantity, ghost) {
          const rf = tpl('tpl-item-row');
          if (ghost) rf.classList.add('ghost-row');
          const cb = rf.querySelector('.dummy-check');
          const nIn = rf.querySelector('[data-cell="name"]');
          const aIn = rf.querySelector('[data-cell="amount"]');
          const qIn = rf.querySelector('[data-cell="quantity"]');
          nIn.value = name || ''; aIn.value = amount || ''; qIn.value = quantity || ''; cb.checked = true;
          const rm = rf.querySelector('.dummy-remove');
          const inputs = [nIn, aIn, qIn];
          body.append(rf);

          function makeReal() {
            const t = group.rowToggle(cb, inputs);
            const entry = { nIn, aIn, qIn, isOn: t.isOn };
            rows.push(entry);
            rm.addEventListener('click', () => {
              const i = rows.indexOf(entry); if (i >= 0) rows.splice(i, 1);
              t.remove(); rf.remove(); sync();
            });
            inputs.forEach((inp) => inp.addEventListener('input', sync));
          }
          if (ghost) {
            const promote = () => {
              if (inputs.every((inp) => inp.value === '')) return;
              inputs.forEach((inp) => inp.removeEventListener('input', promote));
              rf.classList.remove('ghost-row');
              makeReal(); sync();
              addItem('', '', '', true);
            };
            inputs.forEach((inp) => inp.addEventListener('input', promote));
          } else {
            makeReal();
          }
        }

        (initialItems || []).forEach((it) => addItem(String(it.name || ''), numStr(it.amount), numStr(it.quantity), false));
        addItem('', '', '', true);

        return () => {
          const out = [];
          rows.forEach((r) => {
            if (!r.isOn()) return;
            const name = r.nIn.value.trim();
            if (!name) return;
            out.push({ name, amount: r.aIn.value.trim(), quantity: r.qIn.value.trim() });
          });
          return out;
        };
      }

      // ---- Fixed-key cards (receipt / transaction) --------------------
      function fixedCard(title, hint, specs) {
        const group = makeToggleGroup(sync);
        const { card, bulkCb } = buildCard(editor, title, hint);
        group.bulk(bulkCb);
        const body = el('div', 'dummy-rows');
        card.append(body);
        const fields = {};
        specs.forEach(({ key, label, value }) => {
          const rf = tpl('tpl-fixed-row');
          const cb = rf.querySelector('.dummy-check');
          rf.querySelector('.fixed-label').textContent = label;
          const input = rf.querySelector('[data-cell="value"]');
          input.value = value || ''; cb.checked = true;
          body.append(rf);
          const t = group.rowToggle(cb, [input]);
          input.addEventListener('input', sync);
          fields[key] = { input, isOn: t.isOn };
        });
        return () => {
          const out = {};
          Object.entries(fields).forEach(([k, f]) => { if (!f.isOn()) return; if (f.input.value.trim()) out[k] = f.input.value; });
          return out;
        };
      }

      this._receipt = fixedCard('Receipt', 'RFID (top-left) · info title (after header)', [
        { key: 'rfid', label: 'RFID', value: String(data.rfid == null ? '' : data.rfid) },
        { key: 'info_title', label: 'Info Title', value: String(data.info_title == null ? '' : data.info_title) },
      ]);
      this._header = kvCard('Header Info', 'printed above the items', data.header_info || {});
      this._items = itemsCard(data.items || []);
      this._footer = kvCard('Footer Info', 'printed below the total', data.footer_info || {});
      this._tx = fixedCard('Transaction Info', 'leave blank to auto-calculate', [
        { key: 'received', label: 'Received', value: numStr((data.transaction_info || {}).received) },
        { key: 'change', label: 'Change', value: numStr((data.transaction_info || {}).change) },
        { key: 'discount', label: 'Discount', value: numStr((data.transaction_info || {}).discount) },
        { key: 'total', label: 'Total', value: numStr((data.transaction_info || {}).total) },
      ]);

      this._mounted = true;
      if (App.preview) App.preview.refreshNow();
    },

    // Wire the static Reset/Reload buttons once.
    init() {
      const self = this;
      const reset = document.getElementById('dummy-reset');
      const reload = document.getElementById('dummy-reload');
      if (reset) reset.addEventListener('click', async () => {
        const def = await App.bridge.call('get_dummy_defaults');
        S().setDummy(normalize(def));
        self.render();
        App.dom.toast('Loaded defaults — Save to apply');
      });
      if (reload) reload.addEventListener('click', async () => {
        const disk = await App.bridge.call('get_dummy');
        S().setDummy(normalize(disk));
        self.render();
        App.dom.toast('Reloaded from file');
      });
    },

    collect() {
      if (!this._items) return S().dummy || {};
      const payload = {};
      Object.assign(payload, this._receipt());
      const header = this._header();
      if (Object.keys(header).length) payload.header_info = header;

      const items = [];
      this._items().forEach((raw) => {
        const a = parseFloat(raw.amount);
        const q = parseFloat(raw.quantity);
        if (!isNaN(a) && !isNaN(q)) items.push({ name: raw.name, amount: a, quantity: q });
      });
      payload.items = items;

      const footer = this._footer();
      if (Object.keys(footer).length) payload.footer_info = footer;

      const tx = {};
      Object.entries(this._tx()).forEach(([k, v]) => {
        const n = parseFloat(v);
        if (!isNaN(n)) tx[k] = n;
      });
      if (Object.keys(tx).length) payload.transaction_info = tx;
      return payload;
    },
  };
})(window.App);
