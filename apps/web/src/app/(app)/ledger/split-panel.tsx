'use client';
import { useId, useState } from 'react';
import { displayTag, parseTag, plain } from '@/common';
import { Button, ErrorLine, Field, Segmented, TextLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import { type LedgerRow, splitBody, splitCaption, type TagChoice, validateSplit } from '@/features/ledger';
import { useAmountField } from '@/lib/use-amount-field';
import s from './page.module.css';

/** Split an Unaccounted entry: this part goes to a tag, the rest stays Unaccounted until it is fully split. */
export function SplitPanel({ row, choices, onSplit, onClose }: {
  row: LedgerRow; choices: TagChoice[]; onSplit: () => void; onClose: () => void;
}) {
  const id = useId();
  const part = useAmountField('', { decimals: true });
  const [to, setTo] = useState(choices[0]?.name ?? '');
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const check = validateSplit(row.amountMinor, part.paise);
  const parsed = typed.trim() ? parseTag(typed) : null;
  const name = parsed ? (parsed.ok ? parsed.tag : '') : to;
  const target = choices.find((c) => c.name === name) ?? { name };

  async function submit() {
    setBusy(true); setError('');
    try {
      await api.post(`/transactions/${row.id}/split`, splitBody(row.amountMinor, part.paise, target));
      onSplit();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  return (
    <form className="well rise" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); if (check.ok && name) void submit(); }}>
      <div className="lbl">Split the Unaccounted ₹{plain(row.amountMinor)}</div>
      <div className={s.splitRow}>
        <div className={s.splitPart}>
          <label htmlFor={id} className="lbl">This part · ₹</label>
          <input id={id} className={`${s.splitInput} mono`} placeholder="0" {...part.inputProps} />
        </div>
        <div>
          <div className="lbl">Goes to</div>
          <div className={s.goesTo}>
            {choices.length > 0 && <Segmented label="Tag for this part" value={to} onChange={setTo} options={choices.map((c) => ({ value: c.name, label: displayTag(c.name) }))} />}
            <Field label="Or a tag" placeholder="#tag" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
          </div>
        </div>
        <Button type="submit" disabled={!check.ok || !name || busy}>Split</Button>
        <TextLink mono onClick={onClose}>Close</TextLink>
      </div>
      <div className="mono lbl" style={{ marginTop: 8, textTransform: 'none' }}>{splitCaption(check.restMinor)}</div>
      {error && <ErrorLine>{error}</ErrorLine>}
    </form>
  );
}
