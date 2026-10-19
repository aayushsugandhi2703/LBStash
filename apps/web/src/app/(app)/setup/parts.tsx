'use client';
import type { ReactNode } from 'react';
import { StatusLine } from '@/components/ui';
import { copyToClipboard, useFlash } from '@/lib/browser';
import s from './page.module.css';

/** Small pieces the setup steps share. They only compose the global classes and tokens. */

/** One numbered row of step 1 or 2: number, title, explanation, control block, optional checkbox on the far right. */
export function StepRow({ n, title, text, check, children }: { n: number; title: string; text: ReactNode; check?: ReactNode; children?: ReactNode }) {
  return (
    <div className={s.step}>
      <span className={`mono lbl ${s.num}`}>{String(n).padStart(2, '0')}</span>
      <div className={s.stepBody}>
        <div className="row-title">{title}</div>
        <div className={`cap ${s.stepText}`}>{text}</div>
        {children}
      </div>
      {check}
    </div>
  );
}

const TICK = <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;

/** A personal to-do tick: it does not feed the step state. */
export function Checkbox({ n, checked, onChange }: { n: number; checked: boolean; onChange: (v: boolean) => void }) {
  return <button type="button" role="checkbox" aria-checked={checked} aria-label={`Mark step ${n} done`} className={s.check} onClick={() => onChange(!checked)}>{TICK}</button>;
}
/** The read-only box that mirrors a real event (the test message). */
export function MirrorBox({ on }: { on: boolean }) {
  return <span aria-hidden="true" className={s.check} data-on={on} data-static="true">{TICK}</span>;
}

/** Copy link: writes the value to the clipboard and reads `copied` for 1.6 s. `chip` is the quiet variant inside keyword chips. */
export function CopyLink({ value, chip }: { value: string; chip?: boolean }) {
  const [flags, flash] = useFlash();
  const copy = () => void copyToClipboard(value).then((ok) => ok && flash('v'));
  return <button type="button" className={chip ? s.kwCopy : `link mono ${s.copy}`} onClick={copy}>{flags.v ? 'copied' : 'copy'}</button>;
}

/** A status line (waiting or done) with mono text and optional trailing content. */
export function Live({ kind, children, extra }: { kind: 'ok' | 'wait'; children: ReactNode; extra?: ReactNode }) {
  return <div className={s.live}><StatusLine kind={kind}><span className="mono">{children}</span></StatusLine>{extra}</div>;
}

/** The yellow-bulleted notice (this page uses yellow for notices). */
export function Note({ children }: { children: ReactNode }) {
  return <div className={s.note}><i aria-hidden="true" /><span>{children}</span></div>;
}
