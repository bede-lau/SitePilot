/**
 * Three-state theme (light / dark / system), persisted to localStorage and applied to
 * `documentElement` via `data-theme`. `system` stores no explicit override — the token CSS
 * falls back to `prefers-color-scheme` (see design/tokens.css). Paired with the inline script
 * in index.html so the correct theme applies before first paint (no flash).
 */

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "sitepilot-theme";

export function getStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // localStorage unavailable (privacy mode, SSR) — fall through to default.
  }
  return "system";
}

export function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function resolveTheme(pref: ThemePreference): ResolvedTheme {
  return pref === "system" ? getSystemTheme() : pref;
}

/** Applies the preference to the document. `system` clears the explicit attribute. */
export function applyTheme(pref: ThemePreference): void {
  const root = document.documentElement;
  if (pref === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", pref);
  }
  root.style.colorScheme = resolveTheme(pref);
}

export function setThemePreference(pref: ThemePreference): void {
  try {
    localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // ignore — theme just won't persist this session
  }
  applyTheme(pref);
}

/** Matches the inline bootstrap script in index.html — keep them in sync. */
export const THEME_BOOTSTRAP_SCRIPT = `
(function () {
  try {
    var pref = localStorage.getItem('${STORAGE_KEY}');
    var root = document.documentElement;
    if (pref === 'light' || pref === 'dark') {
      root.setAttribute('data-theme', pref);
      root.style.colorScheme = pref;
    } else {
      var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.style.colorScheme = dark ? 'dark' : 'light';
    }
  } catch (e) {}
})();
`.trim();
