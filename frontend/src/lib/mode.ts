/** Colour mode. `system` follows the device; the choice is saved in this browser only, under `MODE_KEY`. */
export type Mode = 'system' | 'light' | 'dark';
export const MODE_KEY = 'lbstash-mode';
export const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

/** Page background per mode, for the browser's address bar (`--surface`). */
const BAR_COLOUR = { light: '#FFFFFF', dark: '#0E0E10' } as const;

/** Runs in <head> before the first paint, so a dark page never flashes white. Keep in step with `applyMode` below. */
export const MODE_SCRIPT = `(function(){try{var m=localStorage.getItem('${MODE_KEY}');var d=m==='dark'||(m!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.mode=d?'dark':'light'}catch(e){}})()`;

export function storedMode(): Mode {
  try {
    const v = window.localStorage.getItem(MODE_KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch { return 'system'; }
}

/** Sets `data-mode` on <html> and tints the address bar to match. */
export function applyMode(mode: Mode): void {
  const dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const resolved = dark ? 'dark' : 'light';
  document.documentElement.dataset.mode = resolved;
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    meta.removeAttribute('media'); // an explicit choice beats the device setting the tag was written for
    meta.content = BAR_COLOUR[resolved];
  });
}

export function saveMode(mode: Mode): void {
  try {
    if (mode === 'system') window.localStorage.removeItem(MODE_KEY); else window.localStorage.setItem(MODE_KEY, mode);
  } catch { /* private window: the choice lasts until the page closes */ }
  applyMode(mode);
}
