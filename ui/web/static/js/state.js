// Working state: config + dummy payload, dirty tracking, change notifications.
window.App = window.App || {};
(function (App) {
  const clone = (o) => (o == null ? o : JSON.parse(JSON.stringify(o)));
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  App.clone = clone;
  App.equal = equal;

  App.state = {
    schema: null,
    config: null, // working copy of the full settings tree
    baseline: null, // last-saved settings (for dirty compare)
    dummy: null, // working copy of the dummy payload
    dummyBaseline: null,
    activeSection: 'LAYOUT',
    locale: 'en',
    _listeners: [],

    setField(section, key, value) {
      if (!this.config[section]) this.config[section] = {};
      this.config[section][key] = value;
      this.emit();
    },

    getField(section, key) {
      return (this.config[section] || {})[key];
    },

    setDummy(next) {
      this.dummy = next;
      this.emit();
    },

    configDirty() {
      return !equal(this.config, this.baseline);
    },
    dummyDirty() {
      return this.dummy != null && !equal(this.dummy, this.dummyBaseline);
    },
    isDirty() {
      return this.configDirty() || this.dummyDirty();
    },

    onChange(fn) {
      this._listeners.push(fn);
    },
    emit() {
      this._listeners.forEach((fn) => fn());
    },

    commitConfig() {
      this.baseline = clone(this.config);
    },
    commitDummy() {
      this.dummyBaseline = clone(this.dummy);
    },
    revert() {
      this.config = clone(this.baseline);
      if (this.dummyBaseline != null) this.dummy = clone(this.dummyBaseline);
      this.emit();
    },
  };
})(window.App);
