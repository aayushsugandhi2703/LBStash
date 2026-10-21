'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import type { DismissUnparsedRes, ResolveUnparsedRes } from '@/contracts';
import { Button, ErrorLine, Segmented, StatusLine, TextLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import { useAmountField } from '@/lib/use-amount-field';
import { canAdd, type Dir, type Done, doneText, initialForm, REASON_TEXT, resolveBody, type UnreadItem, whenLine } from '@/features/unread';
import s from './message.module.css';

type Resolved = z.infer<typeof ResolveUnparsedRes>;
type Dismissed = z.infer<typeof DismissUnparsedRes>;

/** How long Undo stays on offer: the entry is only written after this, so Undo really takes it back. */
const UNDO_MS = 6000;
const DIRECTIONS: { value: Dir; label: string }[] = [{ value: 'debit', label: 'Money out' }, { value: 'credit', label: 'Money in' }];

/** One unread message: the original text, the form that says what it was, and the line that replaces the form once the user acts. */
export function Message({ item, tz, onStatus, onSettled }: {
  item: UnreadItem; tz: string | undefined; onStatus: (id: string, done: Done) => void; onSettled: () => void;
}) {
  const init = initialForm(item);
  const [dir, setDir] = useState<Dir>(init.dir);
  const amount = useAmountField(init.amount, { decimals: true });
  const [name, setName] = useState(init.name);
  const [done, setDone] = useState<Done>('');
  const [settled, setSettled] = useState(false);
  const [tagged, setTagged] = useState<string | null | undefined>(undefined);
  const [error, setError] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const commitRef = useRef<(() => Promise<void>) | null>(null);

  async function commit(kind: Exclude<Done, ''>) {
    commitRef.current = null;
    try {
      if (kind === 'added') {
        const res = await api.post<Resolved>(`/unparsed/${item.id}/resolve`, resolveBody({ dir, name }, amount.paise));
        setTagged(res.transaction.categoryName);
      } else {
        await api.post<Dismissed>(`/unparsed/${item.id}/dismiss`);
      }
      setSettled(true);
      onSettled();
    } catch (e) {
      setDone(''); onStatus(item.id, '');
      setError(errorText(e, 'Could not save that. Your answers are kept. Try again.'));
    }
  }

  function choose(kind: Exclude<Done, ''>) {
    setError('');
    setDone(kind); onStatus(item.id, kind);
    commitRef.current = () => commit(kind);
    timer.current = setTimeout(() => void commitRef.current?.(), UNDO_MS);
  }
  function undo() {
    clearTimeout(timer.current);
    commitRef.current = null;
    setDone(''); onStatus(item.id, '');
  }
  useEffect(() => () => { clearTimeout(timer.current); void commitRef.current?.(); }, []);

  const form = { dir, name, done };
  return (
    <div className={`rise ${s.item}`}>
      {done === '' ? (
        <>
          <div className={`mono lbl ${s.when}`}>{whenLine(item.receivedAt, tz)} · <span className={s.reason}>{REASON_TEXT[item.reason]}</span></div>
          <div className={`mono ${s.text}`}>{item.text}</div>
          <div className={s.controls}>
            <div>
              <div className="lbl">This was</div>
              <div className={s.seg}><Segmented<Dir> label="Direction" value={dir} options={DIRECTIONS} onChange={setDir} /></div>
            </div>
            <div className={s.amount}>
              <label htmlFor={`amt-${item.id}`} className="lbl">Amount ₹</label>
              <input id={`amt-${item.id}`} className={`${s.input} mono`} placeholder="0" {...amount.inputProps} />
            </div>
            <div className={s.payee}>
              <label htmlFor={`name-${item.id}`} className="lbl">Paid to · optional</label>
              <input id={`name-${item.id}`} className={s.input} placeholder="who it was" autoComplete="off" maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          </div>
          <div className={s.actions}>
            <Button disabled={!canAdd(amount.paise)} onClick={() => choose('added')}>Add to the transactions</Button>
            <button type="button" className={`link mono ${s.delete}`} onClick={() => choose('dismissed')}>Not a payment, delete it</button>
          </div>
          {error && <ErrorLine>{error}</ErrorLine>}
        </>
      ) : (
        <div className={s.done}>
          <StatusLine>{doneText(form, amount.paise, tagged)}</StatusLine>
          <span className={s.doneLinks}>
            {done === 'added' && <Link href="/money?cat=needs-tag" className="link mono">tag it in Money →</Link>}
            {!settled && <TextLink mono onClick={undo}>Undo</TextLink>}
          </span>
        </div>
      )}
    </div>
  );
}
