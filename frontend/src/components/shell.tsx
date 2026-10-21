'use client';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { monthProgress, TZ } from '@/common';
import { api } from '@/lib/api';
import { useMe } from '@/lib/me';
import { Glyph, type IconName, LogoMark, NavIcon } from '@/brand';
import { IndexList } from './ui';

type Home = 'now' | 'money' | 'budget' | 'forecast' | 'acct' | null;

const NAV: { key: Home & string; label: string; href: string; icon: IconName }[] = [
  { key: 'now', label: 'Now', href: '/', icon: 'now' },
  { key: 'money', label: 'Money', href: '/money', icon: 'money' },
  { key: 'budget', label: 'Budget', href: '/budget', icon: 'budget' },
  { key: 'forecast', label: 'Forecast', href: '/forecast', icon: 'forecast' },
];

interface ShellProps {
  /** Which nav item is lit. Child pages light their parent (Needs a look → money); Setup lights none. */
  home: Home;
  glyph: IconName;
  title: string;
  description?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
}

/** Signed-in frame: header (icon nav, Account menu, month ruler) over aside + main. One per page. */
export function AppShell({ home, glyph, title, description, aside, children }: ShellProps) {
  return (
    <div className="app">
      <Header home={home} />
      <DemoBar />
      <div className="scroller">
        <aside className="aside">
          <Glyph name={glyph} />
          <h1 className="page-title">{title}</h1>
          {description && <p className="aside-desc opt">{description}</p>}
          {aside}
        </aside>
        <main className="main">{children}</main>
      </div>
    </div>
  );
}

/** Leave the demo: end its session and open the About page (a full load, so no cached Now page is shown). */
async function leaveDemo() {
  try { await api.post('/auth/logout'); } catch { /* the cookie is gone either way once the server answers */ }
  window.location.assign('/');
}

/** Sits under the header while the sample-data demo account is open. */
function DemoBar() {
  const { data: me } = useMe();
  if (!me?.demo) return null;
  return (
    <div className="demo-bar" role="status">
      <span>You are looking at a demo with sample data. It is read-only.</span>
      <span className="demo-bar-links">
        <Link href="/create-account" className="link">Create your own account</Link>
        <button type="button" className="link" onClick={() => void leaveDemo()}>Exit demo</button>
      </span>
    </div>
  );
}

function Header({ home }: { home: Home }) {
  const { data: me } = useMe();
  const tz = me?.timezone ?? TZ;
  return (
    <header className="hdr">
      <div className="hdr-row">
        <div className="hdr-left">
          <Link href="/" className="brand-link" aria-label="LBStash home"><LogoMark size={22} /></Link>
          <nav aria-label="Main" className="nav">
            {NAV.map((n) => (
              <Link key={n.key} href={n.href} className="navlink" aria-current={home === n.key ? 'page' : undefined}>
                <NavIcon name={n.icon} />{n.label}
                {n.key === 'money' && me && me.untaggedCount > 0 && <span className="badge mono">{me.untaggedCount}</span>}
              </Link>
            ))}
          </nav>
        </div>
        <div className="hdr-right">
          <AccountMenu acctPage={home === 'acct'} />
        </div>
      </div>
      <MonthRuler tz={tz} />
    </header>
  );
}

function MonthRuler({ tz }: { tz: string }) {
  // computed after mount so server and client agree (the server's clock/zone may differ)
  const [p, setP] = useState<ReturnType<typeof monthProgress> | null>(null);
  useEffect(() => setP(monthProgress(new Date(), tz)), [tz]);
  const days = p?.days ?? 31;
  const today = p?.day ?? 0;
  return (
    <div className="ruler-row">
      <div className="ruler-label mono">{p ? `day ${today} of ${days}` : ' '}</div>
      <div className="ruler" aria-hidden="true">
        {Array.from({ length: days }, (_, i) => {
          const d = i + 1;
          const show = d === today || ([1, 10, 20, days].includes(d) && Math.abs(d - today) > 2);
          return <span key={d} className="tick" data-past={d < today} data-today={d === today}>{show && <span className="tn mono">{d}</span>}</span>;
        })}
      </div>
    </div>
  );
}

const MENU: { label: string; href: string; hint: string }[] = [
  { label: 'Profile and preferences', href: '/account', hint: 'name, alerts, data' },
  { label: 'Security', href: '/account/security', hint: 'two-step, passkeys' },
  { label: 'Devices and Telegram', href: '/account/devices', hint: 'bot, token' },
  { label: 'Setup guide', href: '/setup', hint: '3 steps' },
  { label: 'Needs a look', href: '/money/unread', hint: '' },
];

function AccountMenu({ acctPage }: { acctPage: boolean }) {
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const path = usePathname();
  const router = useRouter();
  const initial = (me?.name ?? me?.email ?? 'A').charAt(0).toUpperCase();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); btn.current?.focus(); } };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  async function signOut() {
    if (me?.demo) { await leaveDemo(); return; }
    try { await api.post('/auth/logout'); } catch { /* the cookie is gone either way once the server answers */ }
    router.replace('/sign-in');
  }

  return (
    <div style={{ position: 'relative' }}>
      <button ref={btn} type="button" className="acct" data-on={open || acctPage} data-page={acctPage} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span aria-hidden="true" className="avatar mono">{initial}</span>Account
        <svg aria-hidden="true" className="chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <>
          <button type="button" aria-label="Close menu" className="menu-scrim" onClick={() => setOpen(false)} />
          <div role="menu" aria-label="Account" className="menu">
            <div className="menu-id">
              <span aria-hidden="true" className="avatar mono">{initial}</span>
              <span style={{ minWidth: 0 }}>
                <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{me?.name ?? 'Account'}</span>
                <span className="mono" style={{ display: 'block', fontSize: 'var(--fs-label)', color: 'var(--muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{me?.email ?? ''}</span>
              </span>
            </div>
            {MENU.map((m) => {
              const hint = m.href === '/money/unread' ? (me ? `${me.needsLookCount} message${me.needsLookCount === 1 ? '' : 's'}` : '') : m.hint;
              return (
                <Link key={m.href} role="menuitem" href={m.href} className="mi" aria-current={path === m.href ? 'page' : undefined} onClick={() => setOpen(false)}>
                  <span>{m.label}</span><span className="hint mono">{hint}</span>
                </Link>
              );
            })}
            <button role="menuitem" type="button" className="mi signout" onClick={signOut}><span>Sign out</span><span className="hint mono">this browser</span></button>
            <div className="menu-foot mono">renews while you use it</div>
          </div>
        </>
      )}
    </div>
  );
}

/** The three Account pages share this: aside index of sibling pages, main header (label, h2, lead), scrolling body. */
export function AccountShell({ page, glyph, title, description, label, heading, lead, children, summary }: {
  page: 'profile' | 'security' | 'devices'; glyph: IconName; title: string; description: string; label: string; heading: string; lead: string; children: ReactNode; summary?: ReactNode;
}) {
  return (
    <AppShell
      home="acct" glyph={glyph} title={title} description={description}
      aside={
        <div style={{ marginTop: 24 }}>
          <div className="lbl" style={{ paddingBottom: 8 }}>Your account</div>
          <IndexList label="Account pages" items={[
            { key: 'profile', label: 'Profile', href: '/account', active: page === 'profile' },
            { key: 'security', label: 'Security', href: '/account/security', active: page === 'security' },
            { key: 'devices', label: 'Devices and Telegram', href: '/account/devices', active: page === 'devices' },
          ]} />
          {summary && <div className="opt2" style={{ marginTop: 20 }}>{summary}</div>}
        </div>
      }
    >
      <div className="rise" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
        <div className="lbl">{label}</div>
        <h2 className="fig-lg" style={{ marginTop: 4 }}>{heading}</h2>
        <p className="cap" style={{ maxWidth: 680, marginTop: 6 }}>{lead}</p>
        <div style={{ borderTop: '1px solid var(--ink)', marginTop: 'var(--cv-10-2-18)', paddingTop: 'var(--cv-10-2-18)', flex: 1, minHeight: 200, overflowY: 'auto' }}>{children}</div>
      </div>
    </AppShell>
  );
}
