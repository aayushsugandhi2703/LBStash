'use client';
import { useId, useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import type { BalanceCheckRes } from '@/contracts';
import { api, errorText } from '@/lib/api';
import { inrSigned } from '@/common';
import { checkStage } from '@/features/transactions';
import { gapSentence, graceText } from '@/features/now';
import { useAmountField } from '@/lib/use-amount-field';
import { Button, ErrorLine, StatusLine, TextLink } from './ui';
import s from './check-panel.module.css';

type CheckResult = z.infer<typeof BalanceCheckRes>;

/** "Compare with your bank's balance" (ui-spec 02-transactions): the bank's number against the transactions's. */
export function CheckPanel({ transactionsMinor, onChanged, listBelow }: { transactionsMinor: number; onChanged: () => void; listBelow?: boolean }) {
  const id = useId();
  const field = useAmountField('', { decimals: true });
  const [result, setResult] = useState<CheckResult | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const bank = field.paise > 0 ? field.paise : null;
  const stage = result ? checkStage(result) : null;

  async function check() {
    if (bank === null) return;
    setBusy(true); setError(''); setWaiting(false);
    try {
      setResult(await api.post<CheckResult>('/balance-check', { bankBalanceMinor: bank }));
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function book() {
    if (!result) return;
    setBusy(true); setError('');
    try {
      setResult(await api.post<CheckResult>(`/balance-checks/${result.check.id}/book`));
      onChanged();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }

  return (
    <form className={`well rise ${s.panel}`} onSubmit={(e) => { e.preventDefault(); void check(); }}>
      <label htmlFor={id} className="lbl">Balance in your bank app right now · ₹</label>
      <div className={s.row}>
        <input id={id} className={`${s.input} mono`} placeholder="0" {...field.inputProps} onChange={(e) => { field.inputProps.onChange(e); setResult(null); setError(''); }} />
        <Button type="submit" disabled={bank === null || busy}>Check</Button>
      </div>
      <div className={`mono lbl ${s.caption}`} style={{ textTransform: 'none' }}>the transactions says {inrSigned(transactionsMinor)}</div>
      {error && <ErrorLine>{error}</ErrorLine>}
      {result && stage === 'match' && <div className={s.result}><StatusLine>Matches the transactions. Nothing to book.</StatusLine></div>}
      {result && stage === 'gap' && !waiting && (
        <div className={s.result} role="status">
          <div className={s.gap}><span className={s.sq} aria-hidden="true" /><span>{gapSentence(result.check)}</span></div>
          <div className={s.choices}>
            <Button disabled={busy} onClick={() => void book()}>Book it now</Button>
            <TextLink mono onClick={() => setWaiting(true)}>Wait for the message</TextLink>
          </div>
        </div>
      )}
      {result && stage === 'gap' && waiting && (
        <div className={s.result}>
          <StatusLine kind="wait"><span className="mono">
            {result.check.graceEndsAt
              ? `waiting up to ${graceText(Date.parse(result.check.graceEndsAt) - Date.parse(result.check.checkedAt))} for a message, then it books itself`
              : 'waiting for a message, then it books itself'}
          </span></StatusLine>
        </div>
      )}
      {result && stage === 'booked' && (
        <div className={s.result}>
          <StatusLine>
            Booked as Unaccounted. Tag it, or split it, {listBelow ? 'in the list below' : <Link className="link" href="/transactions">in the Transactions</Link>}.
          </StatusLine>
        </div>
      )}
    </form>
  );
}
