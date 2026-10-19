'use client';
import type { ReactNode } from 'react';
import { ErrorLine, StatusLine, TextLink } from '@/components/ui';
import s from './account.module.css';

/** Small pieces the three Account pages share. They only compose the global classes and tokens. */

/** Mono caps header with the ink rule under it. */
export function Section({ first, children }: { first?: boolean; children: ReactNode }) {
  return <div className={`lbl ${s.sec} ${first ? s.first : ''}`}>{children}</div>;
}

/** A status line sitting between two rules, like a row. */
export function LineStatus({ kind = 'ok', children }: { kind?: 'ok' | 'wait' | 'stop'; children: ReactNode }) {
  return <div className={s.line}><StatusLine kind={kind}>{kind === 'stop' ? <span className={s.red}>{children}</span> : children}</StatusLine></div>;
}

/** 9px square for a row title (receiving, signed in …). Always sits next to words. */
export function Sq({ kind = 'ok' }: { kind?: 'ok' | 'wait' | 'stop' }) {
  return <span aria-hidden="true" className={`${s.sq} ${kind === 'ok' ? '' : s[kind]}`} />;
}

/** Inline well under a row: the same grey block as ConfirmWell, for wells that have no lead sentence. */
export function Well({ children }: { children: ReactNode }) {
  return <div className="well" role="group">{children}</div>;
}

/** §10 error state: red line with a plain sentence and one Try again link. */
export function LoadError({ children, retry }: { children?: ReactNode; retry: () => void }) {
  return (
    <div className={s.line}>
      <ErrorLine>{children ?? 'Could not reach the server. Nothing was changed.'}</ErrorLine>
      <div style={{ marginTop: 6 }}><TextLink mono onClick={retry}>Try again</TextLink></div>
    </div>
  );
}
