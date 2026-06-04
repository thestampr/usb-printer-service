// App-level settings (Settings page). These apply immediately (no Save) since
// they're backed by the OS, not the config file — e.g. "Run at startup".
window.App = window.App || {};
(function (App) {
  async function init() {
    const cb = document.getElementById('run-at-startup');
    if (!cb) return;
    const s = await App.bridge.call('get_app_settings');
    cb.checked = !!(s && s.run_at_startup);
    cb.addEventListener('change', async () => {
      const res = await App.bridge.call('set_run_at_startup', cb.checked);
      if (res && res.ok === false) {
        App.dom.toast(res.error || 'Could not update startup setting', 'error');
        cb.checked = !cb.checked; // revert the toggle on failure
        return;
      }
      App.dom.toast(cb.checked ? 'Will run at startup' : 'Startup disabled', 'success');
    });
  }

  App.appsettings = { init };
})(window.App);
