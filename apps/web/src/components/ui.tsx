'use client';
import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, useId } from 'react';
import Link from 'next/link';

/** Shared primitives (design system §4). Pages compose these; they never restyle them. */

export function Button({ large, className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { large?: boolean }) {
  return <button type="button" className={`btn${large ? ' lg' : ''} ${className}`} {...p} />;
}
export function GhostButton({ bad, className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { bad?: boolean }) {
  return <button type="button" className={`ghost${bad ? ' bad' : ''} ${className}`} {...p} />;
}
export function GhostLink({ href, bad, children }: { href: string; bad?: boolean; children: ReactNode }) {
  return <Link href={href} className={`ghost${bad ? ' bad' : ''}`}>{children}</Link>;
}
export function TextLink({ href, onClick, mono, children }: { href?: string; onClick?: () => void; mono?: boolean; children: ReactNode }) {
  const c = `link${mono ? ' mono' : ''}`;
  return href ? <Link href={href} className={c}>{children}</Link> : <button type="button" className={c} onClick={onClick}>{children}</button>;
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} className="switch" onClick={() => onChange(!checked)} />;
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

export function Stepper({ glyph, label, onClick, disabled }: { glyph: string; label: string; onClick: () => void; disabled?: boolean }) {
  return <button type="button" className="stepper" aria-label={label} disabled={disabled} onClick={onClick}>{glyph}</button>;
}

export function Chip({ selected, onClick, children }: { selected?: boolean; onClick?: () => void; children: ReactNode }) {
  return <button type="button" className="chip mono" aria-pressed={selected} onClick={onClick}>{children}</button>;
}

interface IndexEntry {
  key: string; label: string; value?: ReactNode; active?: boolean; href?: string; onClick?: () => void;
  /** Money in is green, money out ink; anything else stays muted. */
  tone?: 'credit' | 'ink' | 'muted';
  /** Accent label (the "Needs a tag" entry). */
  hot?: boolean;
  /** Mini share bar under the label, 0..1 of the biggest item. */
  bar?: number | null;
}

/** Aside filter list: 3px accent bar on the active item, value on the right. `href` makes it a link. */
export function IndexList({ items, label }: { items: IndexEntry[]; label?: string }) {
  return (
    <nav aria-label={label} style={{ marginLeft: 3 }}>
      {items.map((i) => {
        const inner = (
          <>
            <span className={i.hot ? 'hot' : undefined}>{i.label}</span>
            {i.value !== undefined && <span className={`v mono ${i.tone ?? ''}`}>{i.value}</span>}
            {i.bar != null && <span className="idx-bar" aria-hidden="true"><span style={{ width: `${(i.bar * 100).toFixed(1)}%` }} /></span>}
          </>
        );
        return i.href
          ? <Link key={i.key} href={i.href} className="idx" aria-current={i.active ? 'page' : undefined}>{inner}</Link>
          : <button key={i.key} type="button" className="idx" aria-current={i.active ? 'true' : undefined} onClick={i.onClick}>{inner}</button>;
      })}
    </nav>
  );
}

/** Underline input with its caps label above and an optional red error line under it. */
export function Field({ label, error, hint, className = '', ...p }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id} className="lbl">{label}</label>
      <input id={id} className={`uline ${error ? 'err' : ''} ${className}`} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-e` : undefined} {...p} />
      {hint && <div className="cap" style={{ marginTop: 6 }}>{hint}</div>}
      {error && <ErrorLine id={`${id}-e`}>{error}</ErrorLine>}
    </div>
  );
}

/** 6-digit authenticator code: digits only, one-time-code autofill. */
export function CodeInput({ value, onChange, label = 'Authenticator code' }: { value: string; onChange: (v: string) => void; label?: string }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id} className="lbl">{label}</label>
      <input id={id} className="codeinput mono" inputMode="numeric" autoComplete="one-time-code" placeholder="000000" maxLength={6} value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} />
    </div>
  );
}

export function SettingsRow({ title, sub, mono, children }: { title: ReactNode; sub?: ReactNode; mono?: boolean; children?: ReactNode }) {
  return (
    <div className="settings-row">
      <div style={{ minWidth: 0 }}>
        <div className="t">{title}</div>
        {sub && <div className={`s${mono ? ' mono' : ''}`} style={mono ? { fontSize: 'var(--fs-label)' } : undefined}>{sub}</div>}
      </div>
      {children !== undefined && <div style={{ flex: 'none' }}>{children}</div>}
    </div>
  );
}

/** Opens under its row (never a modal): one sentence, then the code input and the confirming button. */
export function ConfirmWell({ text, children }: { text: ReactNode; children: ReactNode }) {
  return <div className="well" role="group"><p>{text}</p><div className="actions">{children}</div></div>;
}

export function StatusLine({ kind = 'ok', children }: { kind?: 'ok' | 'wait' | 'stop'; children: ReactNode }) {
  return <div className="status" data-k={kind} role="status"><span className="sq" aria-hidden="true" /><span>{children}</span></div>;
}
export function ErrorLine({ id, children }: { id?: string; children: ReactNode }) {
  return <div className="err-line" id={id} role="alert"><span className="sq" aria-hidden="true" /><span>{children}</span></div>;
}

export function StripLink({ tag, children, href, onClick, arrow = '→' }: { tag: string; children: ReactNode; href?: string; onClick?: () => void; arrow?: string }) {
  const inner = <><span className="lbl">{tag}</span><span>{children}</span><span aria-hidden="true">{arrow}</span></>;
  return href ? <Link href={href}>{inner}</Link> : <button type="button" onClick={onClick}>{inner}</button>;
}

/** `= available` style block: rows of label/value, last row is the total in accent. */
export function LedgerMath({ rows, total }: { rows: { k: string; v: ReactNode; tone?: 'credit' | 'debit' }[]; total?: { k: string; v: ReactNode } }) {
  return (
    <div className="math mono">
      {rows.map((r) => <div key={r.k} className="r"><span className="k">{r.k}</span><span className={r.tone ?? ''}>{r.v}</span></div>)}
      {total && <div className="r total"><span className="k" style={{ color: 'inherit' }}>{total.k}</span><span className="v">{total.v}</span></div>}
    </div>
  );
}

type BarColour = 'ink' | 'accent' | 'warn' | 'danger';
/** Horizontal progress bar (small 4px / large). Fill colour is semantic and identical everywhere. */
export function ProgressBar({ ratio, colour, size = 's', tick, label }: { ratio: number; colour: BarColour; size?: 's' | 'l'; tick?: number; label?: string }) {
  const w = Math.max(0, Math.min(1, ratio)) * 100;
  return (
    <div className={`bar-track ${size}`} role="img" aria-label={label}>
      <div className="bar-fill" data-c={colour} style={{ width: `${w}%` }} />
      {tick !== undefined && <span className="bar-tick" style={{ left: `${Math.min(100, tick * 100)}%` }} />}
    </div>
  );
}

/** Limit status → bar colour (green under the alert level, yellow at it, red once exceeded; "fast" stays green). */
export const barFor = (s: 'ok' | 'fast' | 'close' | 'over'): BarColour => (s === 'over' ? 'danger' : s === 'close' ? 'warn' : 'accent');

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="empty">{children}{action && <div style={{ marginTop: 12 }}>{action}</div>}</div>;
}

export function Loading({ children = 'loading…' }: { children?: ReactNode }) {
  return <div className="lbl pulse" role="status" style={{ padding: '8px 0' }}>{children}</div>;
}

/** Chart tooltip: wrap a column button in `has-tip` and put this inside it. */
export function Tip({ title, lines, style }: { title: ReactNode; lines?: ReactNode[]; style?: React.CSSProperties }) {
  return <span className="tip mono" role="tooltip" style={style}><span className="t1" style={{ display: 'block' }}>{title}</span>{lines?.map((l, i) => <span key={i} className="t2" style={{ display: 'block' }}>{l}</span>)}</span>;
}

