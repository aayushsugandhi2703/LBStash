import type { ReactNode } from 'react';
import Link from 'next/link';
import { Glyph, type IconName, Logo } from '@/brand';
import s from './auth-frame.module.css';

export function AuthFrame({
  right,
  glyph,
  title,
  description,
  aside,
  children,
}: {
  right: ReactNode;
  glyph: IconName;
  title: string;
  description?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="signin">
      <header className="signin-header">
        <Link href="/" aria-label="LBStash, about"><Logo /></Link>
        <div className="signin-header-right">{right}</div>
      </header>
      <div className="signin-body">
        <aside className="signin-aside">
          <Glyph name={glyph} />
          <h1 className="page-title">{title}</h1>
          {description && <p className="aside-desc opt">{description}</p>}
          {aside}
        </aside>
        <main className="signin-main">{children}</main>
      </div>
    </div>
  );
}

/** The word a sentence turns on (the email name, "used up"). */
export function AuthEm({ children }: { children: ReactNode }) {
  return <strong className={s.em}>{children}</strong>;
}
