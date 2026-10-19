'use client';
import { useState } from 'react';
import type { PatchRecurringReq, RecurringRuleDto } from '@/contracts';
import { ConfirmWell, Empty, ErrorLine, GhostButton, Switch, TextLink } from '@/components/ui';
import { ApiError, errorText } from '@/lib/api';
import { inr } from '@/common';
import { dateLabel, dayAfterNext, formFrom, isEnded, isOn, nextText, patchBody, scheduleSentence, scheduleText } from '@/features/repeats';
import { RuleEditor } from './rule-editor';
import s from './page.module.css';

type Open = { id: string; kind: 'edit' | 'skip' | 'remove' } | null;

interface RulesTableProps {
  rules: RecurringRuleDto[];
  tags: string[];
  onPause: (rule: RecurringRuleDto, paused: boolean) => Promise<void>;
  onChange: (id: string, body: PatchRecurringReq) => Promise<unknown>;
  onSkip: (id: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

/** The rules, one row each: pause switch on the right, change / skip / remove opening a well under the row. */
export function RulesTable({ rules, tags, onPause, onChange, onSkip, onRemove }: RulesTableProps) {
  const [open, setOpen] = useState<Open>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const toggle = (id: string, kind: NonNullable<Open>['kind']) => { setErr(''); setOpen(open?.id === id && open.kind === kind ? null : { id, kind }); };
  async function run(call: () => Promise<void>, done: boolean) {
    setBusy(true); setErr('');
    try { await call(); if (done) setOpen(null); } catch (e) { setErr(e instanceof ApiError && e.status < 500 ? e.message : errorText(e)); } finally { setBusy(false); }
  }

  return (
    <div className={s.tableWrap}>
      <div className={s.tableInner} role="table" aria-label="Repeating payments">
        <div className={`${s.thead} mono lbl`} role="row">
          <div className={s.cPay} role="columnheader">Payment</div>
          <div className={s.cTag} role="columnheader">Tag</div>
          <div className={s.cAmt} role="columnheader">Amount</div>
          <div className={s.cRep} role="columnheader">Repeats</div>
          <div className={s.cNext} role="columnheader">Next</div>
          <div className={s.cOn} role="columnheader">On</div>
        </div>
        {rules.length === 0 && <Empty>No repeating payments yet.</Empty>}
        {rules.map((r) => {
          const mode = open?.id === r.id ? open.kind : null;
          const off = !isOn(r);
          const after = dayAfterNext(r);
          return (
            <div key={r.id} className={`row ${s.rrow}`} role="row">
              <div className={s.line}>
                <div className={s.cPay} role="cell">
                  <div className={s.name} data-off={off}>{r.name}</div>
                  {r.note && <div className="row-sub">{r.note}</div>}
                  <div className={s.acts}>
                    <button type="button" className="link mono" aria-expanded={mode === 'edit'} aria-label={`Change ${r.name}`} onClick={() => toggle(r.id, 'edit')}>Change</button>
                    {!isEnded(r) && <button type="button" className="link mono" aria-expanded={mode === 'skip'} aria-label={`Skip the next ${r.name} payment`} onClick={() => toggle(r.id, 'skip')}>Skip next</button>}
                    <button type="button" className="link mono" aria-expanded={mode === 'remove'} aria-label={`Remove ${r.name}`} onClick={() => toggle(r.id, 'remove')}>Remove</button>
                  </div>
                </div>
                <div className={`${s.cTag} mono`} role="cell" title={r.categoryName} style={{ fontSize: 'var(--fs-s)' }}>#{r.categoryName}</div>
                <div className={`${s.cAmt} mono`} role="cell" style={{ fontSize: 'var(--fs-body)', fontWeight: 500 }}>{inr(r.amountMinor)}</div>
                <div className={`${s.cRep} mono`} role="cell" style={{ fontSize: 'var(--fs-s)', color: 'var(--text-2)' }}>{scheduleText(r.schedule)}</div>
                <div className={`${s.cNext} mono`} role="cell" style={{ fontSize: 'var(--fs-s)', color: 'var(--text-2)' }}>{nextText(r)}</div>
                <div className={s.cOn} role="cell">
                  <Switch
                    checked={!r.paused} disabled={busy || isEnded(r)} label={`${r.paused ? 'Resume' : 'Pause'} ${r.name}`}
                    onChange={(on) => void run(() => onPause(r, !on), false)}
                  />
                </div>
              </div>
              {mode && (
                <div className={s.rowWell}>
                  {mode === 'edit' && (
                    <RuleEditor
                      initial={formFrom(r)} build={patchBody} tags={tags} submitLabel="Save changes"
                      submit={async (body) => { await onChange(r.id, body); setOpen(null); }} onCancel={() => setOpen(null)}
                    />
                  )}
                  {mode === 'skip' && (
                    <ConfirmWell text={`Skip the ${dateLabel(r.nextDue)} payment? It will not be posted.${after ? ` The one after, ${dateLabel(after)}, stays.` : ' That was the last one before its end date.'}`}>
                      <GhostButton disabled={busy} onClick={() => void run(() => onSkip(r.id), true)}>Skip it</GhostButton>
                      <TextLink mono onClick={() => setOpen(null)}>Cancel</TextLink>
                    </ConfirmWell>
                  )}
                  {mode === 'remove' && (
                    <ConfirmWell text={`Remove ${r.name}, ${scheduleSentence(r.schedule)}? It stops posting. Past payments stay. This cannot be undone.`}>
                      <GhostButton bad disabled={busy} onClick={() => void run(() => onRemove(r.id), true)}>Remove payment</GhostButton>
                      <TextLink mono onClick={() => setOpen(null)}>Cancel</TextLink>
                    </ConfirmWell>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {err && <div style={{ paddingTop: 8 }}><ErrorLine>{err}</ErrorLine></div>}
      </div>
    </div>
  );
}
