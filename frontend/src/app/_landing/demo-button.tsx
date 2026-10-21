'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ErrorLine } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { APP_HOME, demoFailure } from '@/features/landing';

/** Starts the read-only demo session (`POST /auth/demo`) and opens the app. `link` is the quiet footer version; `className` adds to the look. */
export function DemoButton({ link = false, className = '', children = 'Try the demo' }: { link?: boolean; className?: string; children?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function open() {
    setBusy(true); setError('');
    try {
      await api.post('/auth/demo');
      router.replace(APP_HOME);
    } catch (e) {
      setError(e instanceof ApiError ? demoFailure(e.status, e.message) : demoFailure(0, ''));
      setBusy(false);
    }
  }

  return (
    <span>
      <button type="button" className={`${link ? 'link' : 'btn lg'} ${className}`} disabled={busy} onClick={() => void open()}>
        {busy ? 'Opening the demo…' : children}
      </button>
      {error && <ErrorLine>{error}</ErrorLine>}
    </span>
  );
}
