// Live receipt preview. The pane structure lives in index.html; this only renders
// the PNG into it, syncs the locale toggle, and matches the floating button width.
window.App = window.App || {};
(function (App) {
  const S = () => App.state;
  const { el, clear } = App.dom;

  let timer = null;
  let lastRun = 0;
  let reqId = 0;
  let lastHash = null;
  let lastPng = null;
  let printBtn = null;
  let localeToggle = null;

  function setLocale(code) {
    S().locale = code;
    if (S().config.LAYOUT) S().setField('LAYOUT', 'receipt_locale', code); // persisted setting
    if (localeToggle) {
      localeToggle.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.value === code));
    }
  }

  function currentPayload() {
    if (App.dummy && App.dummy._mounted && App.dummy.collect) return App.dummy.collect();
    return S().dummy;
  }

  async function onPrintTest() {
    const ok = await App.dom.confirm(
      'Print a test receipt on the selected printer using the current settings?',
      { okLabel: 'Print', cancelLabel: 'Cancel' }
    );
    if (!ok) return;
    const res = await App.bridge.call('test_print', S().config, currentPayload(), S().locale || 'en');
    if (res && res.ok === false) App.dom.toast(res.error || 'Print failed', 'error');
    else App.dom.toast('Test receipt sent to printer', 'success');
  }

  function showImage(src) {
    const wrap = document.getElementById('preview-img-wrap');
    if (!wrap) return;
    clear(wrap);
    const img = el('img');
    img.addEventListener('load', () => {
      requestAnimationFrame(() => {
        if (printBtn) printBtn.style.width = Math.round(img.getBoundingClientRect().width) + 'px';
      });
    });
    img.src = src;
    wrap.append(img);
  }

  function showEmpty(msg) {
    const wrap = document.getElementById('preview-img-wrap');
    if (!wrap) return;
    clear(wrap);
    wrap.append(el('div', 'preview-empty', { textContent: msg }));
  }

  async function build(force) {
    const pane = document.getElementById('preview-pane');
    if (!pane.offsetParent) return; // hidden by the CSS breakpoint / section flag
    const layout = S().config.LAYOUT || {};
    const payload = currentPayload();
    const locale = S().locale || 'en';
    const hash = JSON.stringify([layout, payload, locale]);
    if (!force && hash === lastHash) return;
    lastHash = hash;
    const myId = ++reqId;
    let res;
    try {
      res = await App.bridge.call('render_preview', layout, payload, locale);
    } catch (e) {
      res = { ok: false, error: String(e) };
    }
    if (myId !== reqId) return;
    if (!res || res.ok === false) {
      if (!lastPng) showEmpty('Preview unavailable');
      return;
    }
    lastPng = res.png;
    showImage(res.png);
  }

  const THROTTLE_MS = 140;

  App.preview = {
    init() {
      printBtn = document.getElementById('print-test-btn');
      localeToggle = document.getElementById('locale-toggle');
      if (printBtn) printBtn.addEventListener('click', onPrintTest);
      if (localeToggle) {
        localeToggle.querySelectorAll('button').forEach((b) => {
          b.classList.toggle('active', b.dataset.value === (S().locale || 'en'));
          b.addEventListener('click', () => setLocale(b.dataset.value));
        });
      }
    },
    request(force) {
      const now = typeof performance !== 'undefined' ? performance.now() : 0;
      const wait = THROTTLE_MS - (now - lastRun);
      clearTimeout(timer);
      if (wait <= 0) {
        lastRun = now;
        build(force);
      } else {
        timer = setTimeout(() => {
          lastRun = typeof performance !== 'undefined' ? performance.now() : 0;
          build(force);
        }, wait);
      }
    },
    refreshNow() {
      lastHash = null;
      lastRun = 0;
      this.request(true);
    },
  };
})(window.App);
