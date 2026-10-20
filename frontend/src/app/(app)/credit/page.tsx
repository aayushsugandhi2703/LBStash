'use client';
import { useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import type { CreditRes, CreditsRes, PlanWithSpendDto } from '@/contracts';
import { AppShell } from '@/components/shell';
import { Button, Chip, ErrorLine, Field, TallyMath, Loading, Segmented, Switch, TextLink } from '@/components/ui';
import { api, errorText, fieldErrors, useApi } from '@/lib/api';
import { addRupees, groupIndian, inr, listAmount, monthDay, plain } from '@/common';
import { useToday } from '@/lib/me';
import { cleanTag, creditBody, creditMath, creditTags, type DateChoice, dateText, defaultPickDate, QUICK_ADDS, resolveDate, withTag } from '@/features/credit';
import { rowName } from '@/features/transactions';
import { useAmountField } from '@/lib/use-amount-field';
import s from './page.module.css';

type Credits = z.infer<typeof CreditsRes>;
type Added = z.infer<typeof CreditRes>;
type Plan = z.infer<typeof PlanWithSpendDto>;

/** What was saved, and the figures from before it, so the margin keeps adding up while the success view is on screen. */
interface Done { res: Added; amountMinor: number; tag: string; date: string; balanceBefore: number | null; planBefore: number | null; addedToPlan: boolean }

const DATE_OPTIONS: { value: DateChoice; label: string }[] = [
  { value: 'today', label: 'Today' }, { value: 'yesterday', label: 'Yesterday' }, { value: 'pick', label: 'Pick a date' },
];

export default function CreditPage() {
  const today = useToday();
  // the figures in the margin are read once per visit; the success view keeps its own snapshot
  const recent = useApi<Credits>('/credits?limit=5', { revalidateOnFocus: false });
  const plan = useApi<Plan>(today ? `/plans/${today.month}` : null, { revalidateOnFocus: false });

  const amount = useAmountField();
  const [tag, setTag] = useState('');
  const [added, setAdded] = useState<string[]>([]);
  const [draft, setDraft] = useState('');
  const [choice, setChoice] = useState<DateChoice>('today');
  const [picked, setPicked] = useState('');
  const [note, setNote] = useState('');
  const [addToPlan, setAddToPlan] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<Done | null>(null);

  const tags = added.reduce(withTag, creditTags(recent.data?.items.map((i) => i.categoryName) ?? []));
  const day = today ? resolveDate(choice, today.today, picked || defaultPickDate(today.today)) : '';
  const value = amount.paise;
  const balance = done ? done.balanceBefore : recent.data?.balanceMinor ?? null;
  const planTotal = done ? done.planBefore : plan.data?.totalMinor ?? null;
  const credit = done ? done.amountMinor : value;
  const math = creditMath({ balanceMinor: balance, planMinor: planTotal, creditMinor: credit, addToPlan: done ? done.addedToPlan : addToPlan });
  const figure = (p: number | null) => (p === null ? '—' : plain(p));

  function addTag() {
    const t = cleanTag(draft);
    if (!t) return;
    setTag(t);
    setAdded((a) => withTag(a, t));
    setDraft('');
  }

  async function submit() {
    if (!today || value <= 0 || !tag) return;
    setBusy(true); setError('');
    try {
      const res = await api.post<Added>('/credits', creditBody({ amount: amount.value, tag, date: day, note, addToPlan }));
      setDone({ res, amountMinor: value, tag, date: day, balanceBefore: balance, planBefore: planTotal, addedToPlan: addToPlan });
    } catch (e) {
      setError(Object.values(fieldErrors(e))[0] ?? errorText(e));
    } finally { setBusy(false); }
  }

  function another() {
    setDone(null); amount.setValue(''); setNote(''); setChoice('today'); setError('');
    void recent.mutate();
    void plan.mutate();
  }

  const aside = (
    <>
      <div className={s.mathA}>
        <TallyMath
          rows={[{ k: 'balance now', v: figure(balance) }, { k: '+ this credit', v: plain(credit), tone: 'credit' }]}
          total={{ k: '= new balance', v: <span style={{ color: 'var(--ink)' }}>{figure(math.newBalanceMinor)}</span> }}
        />
      </div>
      <div className={`${s.mathB} opt2`}>
        <TallyMath
          rows={[{ k: 'money to plan', v: figure(planTotal) }, { k: '+ added to plan', v: plain(math.planAddMinor), tone: 'credit' }]}
          total={{ k: '= new plan', v: figure(math.newPlanMinor) }}
        />
      </div>
      <div className={`${s.recent} opt2`}>
        <div className="lbl">Recent credits</div>
        {recent.data?.items.map((c) => (
          <div key={c.id} className={s.recentRow}>
            <span><span className={`mono ${s.recentDate}`}>{monthDay(c.occurredAt, today?.tz)}</span>{rowName(c)}</span>
            <span className={`mono credit ${s.recentAmt}`}>{listAmount(c.amountMinor, 'credit')}</span>
          </div>
        ))}
        {!recent.data && !recent.error && <Loading />}
      </div>
    </>
  );

  return (
    <AppShell
      home="credit" glyph="credit" title="Add credit" aside={aside}
      description="Salary, refunds, gifts and cash. Bank credits add themselves."
    >
      {done ? (
        <div className={s.done} role="status">
          <div className={s.tick} aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </div>
          <div className={`lbl ${s.doneLbl}`}>Credit added</div>
          <div className={`display ${s.doneAmount}`}><span className="rs" style={{ marginRight: 6 }}>₹</span>{plain(done.amountMinor)}</div>
          <p className={`lead ${s.sentence}`}>
            landed in <span className={s.tag}>#{done.tag}</span> on {dateText(done.date)}. Your balance is now <b>{inr(done.res.balanceMinor)}</b>.
          </p>
          <div className={s.doneActions}>
            <Link href="/" className="btn lg">Back to Now</Link>
            <TextLink onClick={another}>Add another</TextLink>
          </div>
        </div>
      ) : (
        <form className={`rise ${s.form}`} onSubmit={(e) => { e.preventDefault(); void submit(); }}>
          <label htmlFor="amt" className="lbl" style={{ flex: 'none' }}>How much came in</label>
          <div className={s.amountRow}>
            <span className={s.rs} aria-hidden="true">₹</span>
            <input id="amt" className={s.amount} placeholder="0" {...amount.inputProps} />
          </div>
          <div className={`${s.quick} opt2`}>
            {QUICK_ADDS.map((n) => (
              <button key={n} type="button" className="link mono" onClick={() => amount.setValue(addRupees(amount.value, n))}>+ {groupIndian(String(n))}</button>
            ))}
          </div>

          <div className={s.cols}>
            <section className={s.source}>
              <div className={`lbl ${s.colHead}`}>Where it came from · a tag</div>
              <div className={s.chips} role="group" aria-label="Tag">
                {tags.map((t) => <Chip key={t} selected={t === tag} onClick={() => setTag(t)}>#{t}</Chip>)}
              </div>
              <div className={s.newTag}>
                <label htmlFor="newtag" className="sr">New tag</label>
                <input
                  id="newtag" placeholder="#tag" autoComplete="off" value={draft}
                  onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                />
                <button type="button" className="link mono" onClick={addTag}>add</button>
              </div>
            </section>
            <section className={s.when}>
              <div className={`lbl ${s.colHead}`}>When</div>
              <div className={s.segWrap}><Segmented<DateChoice> label="Date" value={choice} options={DATE_OPTIONS} onChange={setChoice} /></div>
              <div className={`mono ${s.dateText}`}>{day ? dateText(day) : ' '}</div>
              {choice === 'pick' && today && (
                <>
                  <label htmlFor="dt" className="sr">Pick a date</label>
                  <input id="dt" type="date" className={s.date} value={picked || defaultPickDate(today.today)} max={today.today} onChange={(e) => setPicked(e.target.value)} />
                </>
              )}
            </section>
          </div>

          <div className={s.note}>
            <Field label="Note · optional" autoComplete="off" placeholder="e.g. cash from a friend" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          <div className={`${s.plan} opt`}>
            <div>
              <div className={s.planTitle}>Add it to this month’s plan</div>
              <div className={`cap ${s.planHelp}`}>Raises your “money to plan” so you can give the new money a job.</div>
            </div>
            <Switch checked={addToPlan} onChange={setAddToPlan} label="Add it to this month’s plan" />
          </div>

          {error && <div className={s.failure}><ErrorLine>{error}</ErrorLine></div>}
          <div className={s.actions}>
            <Button large type="submit" disabled={value <= 0 || !tag || !today || busy}>Add credit</Button>
            <Link href="/" className={s.cancel}>Cancel</Link>
            <span className="mono lbl opt" style={{ textTransform: 'none' }}>bank credit alerts add themselves; this page is for cash and everything else</span>
          </div>
        </form>
      )}
    </AppShell>
  );
}
