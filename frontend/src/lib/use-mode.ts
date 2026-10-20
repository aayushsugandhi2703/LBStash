'use client';

import { useCallback, useEffect, useState } from 'react';
import { applyMode, MODE_KEY, type Mode, saveMode, storedMode } from './mode';

/** The saved mode and a setter, for the Account page. Starts as `system` so server and browser render the same first. */
export function useMode(): [Mode, (mode: Mode) => void] {
  const [mode, setMode] = useState<Mode>('system');
  useEffect(() => {
    setMode(storedMode());
    const onStorage = (e: StorageEvent) => { if (e.key === MODE_KEY || e.key === null) { setMode(storedMode()); applyMode(storedMode()); } };
    window.addEventListener('storage', onStorage); // another tab changed it
    return () => window.removeEventListener('storage', onStorage);
  }, []);
  const choose = useCallback((next: Mode) => { setMode(next); saveMode(next); }, []);
  return [mode, choose];
}
