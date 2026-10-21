'use client';
import { useState } from 'react';
import type { z } from 'zod';
import { dateKey, displayTag, parseAmount, plain } from '@/common';
import type { AlertsRes, BudgetDto, BudgetsRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { barFor, Button, ConfirmWell, Empty, ErrorLine, GhostButton, Loading, ProgressBar, SectionTabs, Switch, TextLink } from '@/components/ui';
import { api, errorText, fieldErrors, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { closest, daysLeftText, heading, headline, LEVELS, type LimitChoice, limitChoices, type LimitRow, limitRows, STATE_MARK, warningText } from '@/features/limits';
import { dayLabel } from '@/features/forecast';
import { monthName, type PlanResponse } from '@/features/plan';
import type { RecurringList } from '@/features/repeats';
import s from './page.module.css';

type Budgets = z.infer<typeof BudgetsRes>;
type Alerts = z.infer<typeof AlertsRes>;
interface SettingsLite { alertLevel: number; warnOnPace: boolean }
type Day = NonNullable<ReturnType<typeof useToday>>;

export default function LimitsPage() {
  const today = useToday();
  const month = today?.month;
  const budgets = useApi<Budgets>(month ? `/budgets?month=${month}` : null);
  const settings = useApi<SettingsLite>('/settings');
  const alerts = useApi<Alerts>('/alerts');
  const plan = useApi<PlanResponse>(month ? `/plans/${month}` : null);
  const repeats = useApi<RecurringList>(month ? '/recurring' : null);

  const level = settings.data?.alertLevel ?? budgets.data?.alertLevel ?? 80;
  const warnOnPace = settings.data?.warnOnPace ?? true;
  const rows = budgets.data ? limitRows(budgets.data.items, level, warnOnPace) : null;
  const mName = month ? monthName(month) : 'this month';
  const near = rows && today ? closest(rows, today) : null;
  const choices = plan.data && repeats.data && budgets.data
    ? limitChoices(plan.data.lines, new Set(repeats.data.items.map((r) => r.categoryId)), budgets.data.items)
    : [];
  const daysLeft = today ? daysLeftText(today.day, today.days, mName) : '';

  const [settingsError, setSettingsError] = useState('');
  async function change(patch: Partial<SettingsLite>) {
    if (!settings.data) return;
    setSettingsError('');
    try {
      await settings.mutate(() => api.patch<SettingsLite>('/settings', patch), { optimisticData: { ...settings.data, ...patch }, rollbackOnError: true, revalidate: false });
      void budgets.mutate();
    } catch (e) { setSettingsError(errorText(e, 'Could not save that. Try again.')); }
  }

  const aside = (
    <>
      <div className={s.warnAt}>
        <div className="lbl" style={{ paddingBottom: 8 }}>Warn me at</div>
        <div className={s.lvl} role="group" aria-label="Alert level">
          {LEVELS.map((l) => (
            <button key={l.level} type="button" aria-pressed={l.level === level} onClick={() => void change({ alertLevel: l.level })}>
              <span>{l.level}%</span><small>{l.note}</small>
            </button>
          ))}
        </div>
        <div className={s.pace}>
          <span>Also warn when the pace is too fast</span>
          <Switch checked={warnOnPace} disabled={!settings.data} label="Warn if pace runs over" onChange={(v) => void change({ warnOnPace: v })} />
        </div>
        {settingsError && <ErrorLine>{settingsError}</ErrorLine>}
      </div>
      <div className={`opt2 ${s.recent}`}>
        <div className="lbl">Recent warnings</div>
        {alerts.error && !alerts.data ? (
          <div style={{ paddingTop: 6 }}><ErrorLine>Could not load warnings.</ErrorLine><TextLink mono onClick={() => void alerts.mutate()}>Try again</TextLink></div>
        ) : !alerts.data ? (
          <Loading>loading…</Loading>
        ) : alerts.data.items.length === 0 ? (
          <div className="cap" style={{ marginTop: 6 }}>No warnings yet.</div>
        ) : (
          <div className={`mono ${s.warns}`}>
            {alerts.data.items.slice(0, 3).map((a) => {
              const key = dateKey(new Date(a.sentAt), today?.tz ?? 'Asia/Kolkata');
              return (
                <div key={a.id} data-old={key.slice(0, 7) !== month}>
                  {dayLabel(key.slice(0, 7), Number(key.slice(8)))} · {warningText(a, budgets.data?.items ?? [], level, displayTag)}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );

  return (
    <AppShell home="budget" glyph="budget" title="Budget" description={`Give every rupee of ${mName} a job, then guard the categories that run hot.`} aside={aside}>
      <SectionTabs
        label="Budget"
        hint={`Step 2 of 2. A limit warns you before a category runs out.${daysLeft ? ` ${daysLeft.charAt(0).toUpperCase()}${daysLeft.slice(1)}.` : ''}`}
        tabs={[
          { href: '/budget', label: 'Plan', count: plan.data?.lines.length, active: false },
          { href: '/budget/limits', label: 'Limits', count: rows?.length, active: true },
        ]}
      />

      <p className="lead">
        {rows ? headline(rows, displayTag) : ' '}
        {near && <> {displayTag(near.name)} is the closest: at its pace it hits the limit on <b>{near.date}</b>.</>}
      </p>

      <div className={s.wrap}>
        <div className={s.table} role="table" aria-label={`${mName} limits`}>
          <div className={`${s.lr} ${s.head} th-row lbl`} role="row">
            <span role="columnheader">Category</span>
            <span role="columnheader">Used</span>
            <span className={s.r} role="columnheader">Spent of limit</span>
            <span role="columnheader">State</span>
            <span role="columnheader">Where it is heading</span>
            <span role="columnheader" className="sr">Edit</span>
          </div>
          {budgets.error && !rows ? (
            <div style={{ padding: '12px 0' }}>
              <ErrorLine>{errorText(budgets.error, 'Could not load your limits.')}</ErrorLine>
              <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void budgets.mutate()}>Try again</TextLink></div>
            </div>
          ) : !rows ? (
            <Loading>loading…</Loading>
          ) : rows.length === 0 ? (
            <Empty>No limits yet. Add one below.</Empty>
          ) : (
            rows.map((r) => <LimitItem key={r.id} row={r} month={month} mName={mName} today={today} onChanged={() => budgets.mutate()} />)
          )}
        </div>
      </div>
      <div className={`mono ${s.foot}`}>
        the tick on each bar is where your {level}% warning fires · <TextLink href="/forecast">all categories on the Forecast →</TextLink>
      </div>

      <AddLimit month={month} choices={choices} onAdded={() => void budgets.mutate()} />
    </AppShell>
  );
}

function LimitItem({ row: r, month, mName, today, onChanged }: { row: LimitRow; month: string | undefined; mName: string; today: Day | null; onChanged: () => unknown }) {
  const [mode, setMode] = useState<'edit' | 'remove' | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const name = displayTag(r.name);
  const h = today ? heading(r, today) : null;

  const open = (m: 'edit' | 'remove') => { setErr(''); setText(String(r.limitMinor / 100)); setMode(m); };
  async function run(call: () => Promise<unknown>) {
    setBusy(true); setErr('');
    try { await call(); await onChanged(); setMode(null); } catch (e) { setErr(Object.values(fieldErrors(e))[0] ?? errorText(e)); } finally { setBusy(false); }
  }
  const save = () => {
    const p = parseAmount(text);
    if (p === null) { setErr('Enter a monthly limit like ₹2,000.'); return; }
    return run(() => api.patch<BudgetDto>(`/budgets/${r.id}`, { limitMinor: p }));
  };

  return (
    <div className={s.item}>
      <div className={s.lr} role="row">
        <span className={`row-title ${s.nm}`} role="cell">{name}</span>
        <div className={s.used} role="cell">
          <ProgressBar size="l" ratio={r.ratio} colour={barFor(r.status)} tick={r.alertPct / 100} label={`${name}: ${r.pct}% of the limit spent, alert at ${r.alertPct}%`} />
        </div>
        <div className={`${s.r} ${s.spent}`} role="cell">
          <span className="mono">{plain(r.spentMinor)}</span><span className={`mono ${s.sub}`}> of {plain(r.limitMinor)}</span>
          <div className={`mono ${s.sub}`}>{plain(r.leftMinor)} {r.leftMinor >= 0 ? 'left' : 'over'}</div>
        </div>
        <span className={s.state} data-k={r.status} role="cell"><span aria-hidden="true">{STATE_MARK[r.status]}</span>{r.statusText}</span>
        <div className={s.heading} role="cell">
          {h && (
            <>
              <span className={h.bad ? s.bad : s.good}>{h.text}</span>
              {h.when && <span className={`mono ${s.sub}`}> · {h.when}</span>}
              {h.note && <div className={s.sub}>{h.note}</div>}
            </>
          )}
        </div>
        <div className={s.act} role="cell">
          <button type="button" className={`link ${s.edit}`} aria-expanded={mode !== null} aria-label={`Edit the ${name} limit`} onClick={() => (mode ? setMode(null) : open('edit'))}>Edit</button>
        </div>
      </div>

      {mode === 'edit' && (
        <div className={s.wellWrap}>
          <ConfirmWell text="Raising a limit re-arms its warnings this month.">
            <div className="fld" style={{ width: 180 }}>
              <label className="lbl" htmlFor={`limit-${r.id}`}>Monthly limit</label>
              <input id={`limit-${r.id}`} className="boxin" inputMode="decimal" placeholder="5000" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void save(); }} />
            </div>
            <Button disabled={busy} onClick={() => void save()}>Save limit</Button>
            <TextLink mono onClick={() => void run(() => api.patch<BudgetDto>(`/budgets/${r.id}`, { useMonthAllocation: true, month }))}>Use {mName}&rsquo;s plan</TextLink>
            <TextLink mono onClick={() => open('remove')}>Remove</TextLink>
            <TextLink mono onClick={() => setMode(null)}>Cancel</TextLink>
            {err && <ErrorLine>{err}</ErrorLine>}
          </ConfirmWell>
        </div>
      )}
      {mode === 'remove' && (
        <div className={s.wellWrap}>
          <ConfirmWell text={`Remove the ${name} limit and its warnings? Payments and plan stay as they are.`}>
            <GhostButton bad disabled={busy} onClick={() => void run(() => api.del(`/budgets/${r.id}`))}>Remove limit</GhostButton>
            <TextLink mono onClick={() => setMode(null)}>Cancel</TextLink>
            {err && <ErrorLine>{err}</ErrorLine>}
          </ConfirmWell>
        </div>
      )}
    </div>
  );
}

function AddLimit({ month, choices, onAdded }: { month: string | undefined; choices: LimitChoice[]; onAdded: () => void }) {
  const [tag, setTag] = useState('');
  const [amt, setAmt] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const pick = choices.find((c) => c.tag === tag) ?? choices[0];

  async function submit() {
    if (!pick) return;
    setErr('');
    let body: Record<string, unknown>;
    if (amt.trim()) {
      const p = parseAmount(amt);
      if (p === null) { setErr('Enter a monthly limit like ₹2,000.'); return; }
      body = { tag: pick.tag, limitMinor: p };
    } else if (pick.planMinor > 0) body = { tag: pick.tag, useMonthAllocation: true, month };
    else { setErr('Enter a monthly limit like ₹2,000.'); return; }
    setBusy(true);
    try { await api.post('/budgets', body); setTag(''); setAmt(''); onAdded(); } catch (e) { setErr(Object.values(fieldErrors(e))[0] ?? errorText(e)); } finally { setBusy(false); }
  }

  if (!pick) return <p className={`cap ${s.allSet}`}>Every category on your plan has a limit. Add a category on the Plan tab to limit it too.</p>;
  return (
    <>
      <form className="formrow" aria-label="Add a limit" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <div className="fld">
          <label className="lbl" htmlFor="limit-cat">Add a limit to</label>
          <select id="limit-cat" className={`boxin ${s.sel}`} value={pick.tag} onChange={(e) => setTag(e.target.value)}>
            {choices.map((c) => <option key={c.tag} value={c.tag}>{c.name} (plan {plain(c.planMinor)})</option>)}
          </select>
        </div>
        <div className="fld">
          <label className="lbl" htmlFor="limit-amt">Limit ₹</label>
          <input id="limit-amt" className={`boxin ${s.amt}`} inputMode="decimal" autoComplete="off" placeholder={pick.planMinor > 0 ? `same as plan: ${plain(pick.planMinor)}` : '5000'} value={amt} onChange={(e) => setAmt(e.target.value)} />
        </div>
        <Button type="submit" disabled={busy}>Add limit</Button>
      </form>
      {err && <ErrorLine>{err}</ErrorLine>}
    </>
  );
}
