'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { APP_HOME, hasSessionCookie } from '@/features/landing';
import { DemoButton } from './demo-button';

/** Top-bar links: Sign in plus the demo button, or "Open the app" when this browser already holds a session (read from the JS-readable cookie, after mount). */
export function AccountLinks({ linkClass, demoClass }: { linkClass: string; demoClass: string }) {
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => setSignedIn(hasSessionCookie(document.cookie)), []);
  return signedIn ? (
    <Link href={APP_HOME} className={linkClass} style={{ color: 'var(--accent)' }}>Open the app →</Link>
  ) : (
    <>
      <Link href="/sign-in" className={linkClass}>Sign in</Link>
      <DemoButton className={demoClass} />
    </>
  );
}
