// Service page: Run/Stop the Flask server (detached child, survives close) and
// stream its log file into a colorized, self-scrolling console.
window.App = window.App || {};
(function (App) {
  const { el, clear, icon, toast } = App.dom;

  let toggleBtn = null;
  let stateEl = null;
  let body = null;
  let running = false;
  let busy = false;
  let pollTimer = null;
  const MAX_LINES = 2000;

  // ---- Log line classification -------------------------------------------
  const HTTP_RE = /"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s[^"]*"\s(\d{3})/;

  function levelOf(line) {
    if (/\b(ERROR|CRITICAL)\b|Traceback|Exception/.test(line)) return 'error';
    if (/\bWARN(ING)?\b/.test(line)) return 'warn';
    if (/^\s*\*/.test(line) || /Running on|Serving Flask|Debug mode|Press CTRL/.test(line)) return 'banner';
    if (/\bDEBUG\b/.test(line)) return 'debug';
    if (/\bINFO\b/.test(line)) return 'info';
    return 'plain';
  }

  function statusClass(code) {
    const c = parseInt(code, 10);
    if (c >= 500) return 'error';
    if (c >= 400) return 'warn';
    if (c >= 300) return 'redirect';
    return 'ok';
  }

  // Build one log row, emphasizing the HTTP verb + status code when present.
  function renderLine(line) {
    const m = line.match(HTTP_RE);
    let level = levelOf(line);
    if (m) level = statusClass(m[2]); // a request line is colored by its status
    const row = el('div', 'log-line log-' + level);
    if (m) {
      const i = m.index;
      row.append(document.createTextNode(line.slice(0, i)));
      row.append(el('span', 'log-method', { textContent: '"' + m[1] }));
      const afterVerb = line.slice(i + 1 + m[1].length, i + m[0].length - 3);
      row.append(document.createTextNode(afterVerb));
      row.append(el('span', 'log-code', { textContent: m[2] }));
      row.append(document.createTextNode(line.slice(i + m[0].length)));
    } else {
      row.textContent = line;
    }
    return row;
  }

  // eslint-disable-next-line no-control-regex
  const ANSI_RE = /\x1b\[[0-9;]*m/g;

  function appendLines(raw) {
    if (!body) return;
    let lines = raw.map((l) => l.replace(ANSI_RE, ''));
    const empty = body.querySelector('.console-empty');
    if (empty) empty.remove();
    // Drop leading blank lines so the console starts at the first real output.
    if (!body.querySelector('.log-line')) {
      while (lines.length && lines[0].trim() === '') lines = lines.slice(1);
    }
    if (!lines.length) return;
    const atBottom = body.scrollTop + body.clientHeight >= body.scrollHeight - 6;
    const frag = document.createDocumentFragment();
    lines.forEach((ln) => frag.append(renderLine(ln)));
    body.append(frag);
    // Trim the buffer so a long-running service can't grow the DOM unbounded.
    while (body.childElementCount > MAX_LINES) body.firstElementChild.remove();
    if (atBottom) body.scrollTop = body.scrollHeight;
  }

  function setRunning(state, info) {
    running = !!state;
    const navBtn = document.getElementById('nav-service');
    if (navBtn) navBtn.classList.toggle('service-on', running);
    clear(toggleBtn);
    toggleBtn.append(icon(running ? 'stop' : 'play'));
    toggleBtn.append(document.createTextNode(running ? 'Stop Service' : 'Run Service'));
    toggleBtn.classList.toggle('primary', !running);
    toggleBtn.classList.toggle('danger', running);
    stateEl.classList.toggle('on', running);
    const txt = stateEl.querySelector('.state-text');
    if (running && info && info.host != null) {
      txt.textContent = 'Running · ' + info.host + ':' + info.port;
    } else {
      txt.textContent = running ? 'Running' : 'Stopped';
    }
  }

  async function refreshStatus() {
    const st = await App.bridge.call('service_status');
    setRunning(st && st.running, st);
  }

  async function onToggle() {
    if (busy) return;
    busy = true;
    toggleBtn.disabled = true;
    try {
      if (running) {
        const r = await App.bridge.call('stop_service');
        if (r && r.ok === false) toast(r.error || 'Could not stop service', 'error');
        else toast('Service stopped');
      } else {
        const r = await App.bridge.call('start_service');
        if (r && r.ok === false) { toast(r.error || 'Could not start service', 'error'); }
        else toast('Service started on ' + r.host + ':' + r.port, 'success');
      }
      await refreshStatus();
    } finally {
      busy = false;
      toggleBtn.disabled = false;
    }
  }

  App.service = {
    _push(lines) { appendLines(lines); },
    _reset() { if (body) clear(body); },
    refresh: refreshStatus,

    async init() {
      toggleBtn = document.getElementById('service-toggle');
      stateEl = document.getElementById('service-state');
      body = document.getElementById('service-console');
      toggleBtn.addEventListener('click', onToggle);
      document.getElementById('console-clear').addEventListener('click', () => clear(body));

      // Seed the console with buffered log history, then stream live lines.
      const hist = await App.bridge.call('attach_console');
      if (hist && hist.lines && hist.lines.length) appendLines(hist.lines);
      refreshStatus();
      // Keep the button/state in sync if the service stops/starts elsewhere.
      pollTimer = setInterval(refreshStatus, 3000);
    },
  };
})(window.App);
