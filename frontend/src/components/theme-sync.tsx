'use client';

import { useEffect } from 'react';
import { applyMode, storedMode } from '@/lib/mode';

/** Keeps the page in step with the saved mode: tints the address bar once the page is up, and follows the device when the mode is `system`. */
export function ThemeSync() {
  useEffect(() => {
    applyMode(storedMode());
    const device = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => { if (storedMode() === 'system') applyMode('system'); };
    device.addEventListener('change', onChange);
    return () => device.removeEventListener('change', onChange);
  }, []);
  return null;
}
