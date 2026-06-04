// Thin wrapper over the pywebview js_api bridge.
// Classic script (not an ES module): file:// blocks module scripts in Chromium.
window.App = window.App || {};
(function (App) {
  const ready = new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) {
      resolve();
      return;
    }
    window.addEventListener('pywebviewready', () => resolve(), { once: true });
  });

  App.bridge = {
    ready,
    async call(method, ...args) {
      await ready;
      const fn = window.pywebview.api[method];
      if (typeof fn !== 'function') {
        throw new Error('Unknown bridge method: ' + method);
      }
      return fn(...args);
    },
  };
})(window.App);
