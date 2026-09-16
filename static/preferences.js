/* Runs before CSS to apply saved appearance without a light-theme flash.
   Only developer-authored literals are translated. Business data is never rewritten. */
(() => {
  "use strict";
  const key = "ncs.preferences.v1";
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(key) || "{}") || {};
  } catch (_) {}
  const state = {
    language: ["zh", "en"].includes(saved.language) ? saved.language : "zh",
    theme: ["light", "dark", "system"].includes(saved.theme)
      ? saved.theme
      : "system",
  };
  let dictionary = {};
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  function apply() {
    const theme =
      state.theme === "system"
        ? media.matches
          ? "dark"
          : "light"
        : state.theme;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = state.theme;
    document.documentElement.lang = state.language === "en" ? "en" : "zh-CN";
    document.documentElement.style.colorScheme = theme;
    document.title = translate("NCS SMART CHARGING");
  }
  function set(values, persist = true) {
    if (["zh", "en"].includes(values?.language))
      state.language = values.language;
    if (["light", "dark", "system"].includes(values?.theme))
      state.theme = values.theme;
    apply();
    if (persist) {
      try {
        localStorage.setItem(key, JSON.stringify(state));
      } catch (_) {}
    }
  }
  function translate(value) {
    if (typeof value !== "string" || state.language !== "en") return value;
    if (Object.hasOwn(dictionary, value)) return dictionary[value];
    // Only invoked for source-code literals (including their HTML attributes).
    // Interpolated names, addresses and free text are kept outside this function.
    return value.replace(/[^<>"'\n]*[\u3400-\u9fff][^<>"'\n]*/g, (part) => {
      const core = part.trim();
      if (!Object.hasOwn(dictionary, core)) return part;
      return (
        part.slice(0, part.indexOf(core)) +
        dictionary[core] +
        part.slice(part.indexOf(core) + core.length)
      );
    });
  }
  function template(strings, ...values) {
    return strings.reduce(
      (html, text, i) =>
        html + translate(text) + (i < values.length ? values[i] : ""),
      "",
    );
  }
  const ready = fetch("/static/i18n/en.json?v=20260916a")
    .then((response) => {
      if (!response.ok) throw new Error("Translation file unavailable");
      return response.json();
    })
    .then((data) => {
      dictionary = data;
      apply();
    });
  ready.catch(() => {}); // boot() presents a recoverable error if static files are missing.
  window.NCSPreferences = { state, set, apply, translate, template, ready };
  if (media.addEventListener)
    media.addEventListener("change", () => {
      if (state.theme === "system") apply();
    });
  else
    media.addListener(() => {
      if (state.theme === "system") apply();
    });
  // Tabs in the same browser share appearance; no remote write is triggered here.
  window.addEventListener("storage", (e) => {
    if (e.key !== key) return;
    try {
      set(JSON.parse(e.newValue || "{}"), false);
      window.dispatchEvent(new Event("ncs-preferences-external"));
    } catch (_) {}
  });
  apply();
})();
const tr = (value) => window.NCSPreferences.translate(value);
const trHtml = (strings, ...values) =>
  window.NCSPreferences.template(strings, ...values);

