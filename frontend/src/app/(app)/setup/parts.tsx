'use client';
import type { ReactNode } from 'react';
import { StatusLine } from '@/components/ui';
import { copyToClipboard, useFlash } from '@/lib/browser';
import s from './page.module.css';

/** Small pieces the setup steps share. They only compose the global classes and tokens. */

/** One numbered row of step 1: number, title, explanation, control block. */
export function StepRow({ n, title, text, children }: { n: number; title: string; text: ReactNode; children?: ReactNode }) {
  return (
    <div className={s.step}>
      <span className={`mono lbl ${s.num}`}>{String(n).padStart(2, '0')}</span>
      <div className={s.stepBody}>
        <div className="row-title">{title}</div>
        <div className={`cap ${s.stepText}`}>{text}</div>
        {children}
      </div>
    </div>
  );
}

/** Copy link: writes the value to the clipboard and reads `copied` for 1.6 s. */
export function CopyLink({ value }: { value: string }) {
  const [flags, flash] = useFlash();
  const copy = () => void copyToClipboard(value).then((ok) => ok && flash('v'));
  return <button type="button" className={`link mono ${s.copy}`} onClick={copy}>{flags.v ? 'copied' : 'copy'}</button>;
}

/** A status line (waiting or done) with mono text and optional trailing content. */
export function Live({ kind, children, extra }: { kind: 'ok' | 'wait'; children: ReactNode; extra?: ReactNode }) {
  return <div className={s.live}><StatusLine kind={kind}><span className="mono">{children}</span></StatusLine>{extra}</div>;
}
