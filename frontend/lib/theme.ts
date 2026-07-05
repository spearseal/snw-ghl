export type Theme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'ghl_sf_theme';

export function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

export function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'light' ? 'light' : 'dark';
}

export function storeTheme(theme: Theme) {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}
