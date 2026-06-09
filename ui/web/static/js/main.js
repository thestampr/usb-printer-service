// Bootstraps the UI: loads config, wires the declarative sections, handles nav +
// save/cancel/reset. The forms are HTML (see index.html); this only binds behavior.
window.App = window.App || {};
(function (App) {
  const S = App.state;
  const { toast } = App.dom;

  function titleCase(sec) {
    return sec.charAt(0) + sec.slice(1).toLowerCase();
  }

  const previewMQ = window.matchMedia('(min-width: 1280px)');
  function previewable() {
    return S.activeSection === 'LAYOUT' || S.activeSection === 'DUMMY';
  }
  function updatePreviewVisibility() {
    document.querySelector('.app').classList.toggle('show-preview', previewable());
    if (previewable() && previewMQ.matches && App.preview) App.preview.request();
  }

  function selectSection(sec) {
    S.activeSection = sec;
    document.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.section === sec));
    document.querySelectorAll('.form-section').forEach((s) => s.toggleAttribute('hidden', s.dataset.section !== sec));
    document.getElementById('section-title').textContent = titleCase(sec);
    document.getElementById('dummy-actions').toggleAttribute('hidden', sec !== 'DUMMY');
    if (App.dummy) App.dummy._mounted = sec === 'DUMMY';
    updatePreviewVisibility();
    refreshScrollShadows();
  }

  let lastDirty = null;
  function updateDirty() {
    const dirty = S.isDirty();
    document.getElementById('save-btn').disabled = !dirty;
    document.getElementById('cancel-btn').disabled = !dirty;
    if (dirty !== lastDirty) {
      lastDirty = dirty;
      App.bridge.call('set_dirty', dirty);
    }
  }

  async function save() {
    if (S.dummyDirty() && (!S.dummy.items || S.dummy.items.length === 0)) {
      toast('Add at least one item before saving the dummy payload.', 'error');
      return;
    }
    const res = await App.bridge.call('save_config', S.config);
    if (res && res.ok === false) { toast(res.error || 'Save failed', 'error'); return; }
    if (S.dummyDirty()) {
      const dr = await App.bridge.call('save_dummy', S.dummy);
      if (dr && dr.ok === false) { toast(dr.error || 'Save failed', 'error'); return; }
    }
    S.commitConfig();
    if (S.dummy) S.commitDummy();
    updateDirty();
    toast('Settings saved', 'success');
  }

  function revert() {
    S.revert();
    App.binding.reload();
    if (App.dummy) App.dummy.render();
    updateDirty();
    if (App.preview) App.preview.request();
  }

  async function resetDefaults() {
    const ok = await App.dom.confirm(
      'Reset all settings to defaults? You can still Cancel before saving.',
      { okLabel: 'Reset', cancelLabel: 'Cancel', danger: true }
    );
    if (!ok) return;
    const defaults = await App.bridge.call('get_config_defaults');
    S.config = App.clone(defaults);
    App.binding.reload();
    updateDirty();
    if (App.preview) App.preview.request();
  }

  async function checkUpdate(e) {
    const btn = e.currentTarget;
    // Swap only the label, keeping the leading icon (textContent would wipe the SVG).
    const ic = btn.querySelector('svg');
    const prev = btn.textContent;
    const setLabel = (txt) => { btn.textContent = txt; if (ic) btn.prepend(ic); };
    btn.disabled = true;
    setLabel('Checking…');
    try {
      const res = await App.bridge.call('check_update');
      if (res && res.ok === false) { toast(res.error || 'Update check failed', 'error'); return; }
      if (!res || !res.available) {
        toast('You are up to date (v' + (res && res.current || '?') + ')');
        return;
      }
      let msg = 'Version ' + (res.latest || '?') + ' is available (you have ' +
        (res.current || '?') + '). Install now? The app will close to finish updating.';
      const vi = await App.bridge.call('get_version_info');
      if (vi && vi.is_dev) msg += '\n\nNote: this is a development checkout — updating overwrites local changes.';
      const go = await App.dom.confirm(msg, { okLabel: 'Update', cancelLabel: 'Later' });
      if (!go) return;
      const ur = await App.bridge.call('run_update');
      if (ur && ur.ok === false) toast(ur.error || 'Could not start updater', 'error');
      else toast('Updater started — it will finish once this window closes.');
    } finally {
      btn.disabled = false;
      setLabel(prev);
    }
  }

  function wireNav() {
    document.querySelectorAll('.nav-item').forEach((b) =>
      b.addEventListener('click', () => selectSection(b.dataset.section)));
    document.getElementById('update-btn').addEventListener('click', checkUpdate);
    document.getElementById('link-docs').addEventListener('click', () => App.bridge.call('open_docs'));
    document.getElementById('link-github').addEventListener('click', () => App.bridge.call('open_github'));
  }

  // Toggle a `scrolled` class on a header once its scroll pane leaves the top, so
  // the header's soft shadow only shows when there's content scrolled under it.
  const scrollShadowUpdaters = [];
  function wireScrollShadow(scrollEl, headerSel) {
    const scroll = typeof scrollEl === 'string' ? document.getElementById(scrollEl) : scrollEl;
    const header = document.querySelector(headerSel);
    if (!scroll || !header) return;
    const update = () => header.classList.toggle('scrolled', scroll.scrollTop > 0);
    scroll.addEventListener('scroll', update, { passive: true });
    scrollShadowUpdaters.push(update);
    update();
  }
  // Switching sections can clamp a short pane's scrollTop without firing a scroll
  // event, so re-check after layout settles to clear a stale shadow.
  function refreshScrollShadows() {
    requestAnimationFrame(() => scrollShadowUpdaters.forEach((u) => u()));
  }

  // Called by the native close handler when there are unsaved changes.
  App.confirmClose = async function () {
    const ok = await App.dom.confirm('You have unsaved changes. Close without saving?', {
      okLabel: 'Close',
      cancelLabel: 'Cancel',
      danger: true,
    });
    if (ok) App.bridge.call('request_close');
  };

  // Called when Quit (tray menu) is chosen with unsaved changes.
  App.confirmQuit = async function () {
    const ok = await App.dom.confirm('You have unsaved changes. Quit without saving?', {
      okLabel: 'Quit',
      cancelLabel: 'Cancel',
      danger: true,
    });
    if (ok) App.bridge.call('request_quit');
  };

  async function init() {
    await App.bridge.ready;
    S.config = await App.bridge.call('get_config');
    S.commitConfig();
    S.dummy = await App.bridge.call('get_dummy');
    if (App.dummy) S.dummy = App.dummy.normalize(S.dummy);
    S.commitDummy();
    S.locale = (S.config.LAYOUT && S.config.LAYOUT.receipt_locale) || 'en';

    const vi = await App.bridge.call('get_version_info');
    document.getElementById('nav-version').textContent = vi.current ? 'v' + vi.current : '';

    App.binding.init();
    App.printer.init();
    App.preview.init();
    if (App.service) App.service.init();
    if (App.appsettings) App.appsettings.init();
    if (App.dummy) { App.dummy.init(); App.dummy.render(); }

    wireNav();
    wireScrollShadow('form-pane', '.section-header');
    wireScrollShadow(document.querySelector('.preview-scroll'), '.preview-toolbar');
    document.getElementById('save-btn').addEventListener('click', save);
    document.getElementById('cancel-btn').addEventListener('click', revert);
    document.getElementById('reset-btn').addEventListener('click', resetDefaults);

    S.onChange(() => {
      updateDirty();
      if (App.preview) App.preview.request();
    });
    previewMQ.addEventListener('change', (e) => {
      if (e.matches && previewable() && App.preview) App.preview.request();
    });

    selectSection('LAYOUT');
    updateDirty();

    // Viewport is wired — let one frame paint under the splash, then fade it out.
    requestAnimationFrame(() => requestAnimationFrame(hideSplash));
  }

  // Keep the splash on screen for at least this long so a fast (in-process) init
  // doesn't make it flash. Measured from when the script first runs (~reveal).
  const MIN_SPLASH_MS = 1200;
  const splashStart = (typeof performance !== 'undefined' ? performance.now() : Date.now());

  function hideSplash() {
    const s = document.getElementById('splash');
    if (!s || s.dataset.hiding) return;
    s.dataset.hiding = '1';
    const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const wait = Math.max(0, MIN_SPLASH_MS - (now - splashStart));
    setTimeout(() => {
      s.classList.add('hide');           // triggers the CSS opacity fade-out
      const remove = () => s.remove();
      s.addEventListener('transitionend', remove, { once: true });
      setTimeout(remove, 900);           // fallback if transitionend doesn't fire
    }, wait);
  }

  App.app = { selectSection, updateDirty };

  // Safety net: never leave the splash stuck if init() stalls.
  setTimeout(hideSplash, 8000);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window.App);
