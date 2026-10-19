'use client';
import { useCallback, useEffect, useRef, useState } from 'react';

/** Copy a value to the clipboard; false when the browser refuses. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

/** Save text as a file in the browser (no server round trip). */
export function downloadText(filename: string, text: string, type = 'application/json'): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Flash a label for a moment (`copy` → `copied`). Keys flash independently. */
export function useFlash(ms = 1600) {
  const [keys, setKeys] = useState<Record<string, boolean>>({});
  const timers = useRef<Record<string, number>>({});
  useEffect(() => () => Object.values(timers.current).forEach((t) => window.clearTimeout(t)), []);
  const flash = useCallback((key: string) => {
    window.clearTimeout(timers.current[key]);
    setKeys((k) => ({ ...k, [key]: true }));
    timers.current[key] = window.setTimeout(() => setKeys((k) => ({ ...k, [key]: false })), ms);
  }, [ms]);
  return [keys, flash] as const;
}
