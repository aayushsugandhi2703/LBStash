'use client';
import { useState } from 'react';
import type { z } from 'zod';
import { displayTag, inr, monthDay, parseAmount } from '@/common';
import type { AlertsRes, BudgetDto, BudgetsRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { barFor, Button, ConfirmWell, Empty, ErrorLine, Field, GhostButton, IndexList, Loading, ProgressBar, Switch, TextLink } from '@/components/ui';
import { api, errorText, fieldErrors, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { daysLeftText, headline, LEVELS, type LimitRow, limitRows, warningText } from '@/features/limits';
import { monthName } from '@/features/plan';
import s from './page.module.css';

type Budgets = z.infer<typeof BudgetsRes>;
type Alerts = z.infer<typeof AlertsRes>;
interface SettingsLite { alertLevel: number; warnOnPace: boolean }

export default function LimitsPage() {
  const today = useToday();
  const month = today?.month;
  const budgets = useApi<Budgets>(month ? `/budgets?month=${month}` : null);
  const settings = useApi<SettingsLite>('/settings');
  const alerts = useApi<Alerts>('/alerts');
  const cats = useApi<{ items: { name: string; archived: boolean }[] }>('/categories');

  const level = settings.data?.alertLevel ?? budgets.data?.alertLevel ?? 80;
  const warnOnPace = settings.data?.warnOnPace ?? true;
  const rows = budgets.data ? limitRows(budgets.data.items, level, warnOnPace) : null;
  const mName = month ? monthName(month) : 'this month';

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
      <div className={`lbl ${s.sectionLbl}`}>Warn me when a limit is</div>
      <IndexList
        label="Alert level"
        items={LEVELS.map((l) => ({ key: String(l.level), label: `${l.level}% used`, value: l.note, active: l.level === level, onClick: () => void change({ alertLevel: l.level }) }))}
      />
      {settingsError && <ErrorLine>{settingsError}</ErrorLine>}
      <div className={`opt2 ${s.how}`}>
        <div className={`lbl ${s.sectionLbl}`} style={{ marginTop: 0 }}>How</div>
        <div className={s.howRow}>
          <span>Send alerts to Telegram</span>
          {/* Alerts only ever go to Telegram; the API has no switch for it, so this one shows the fact and cannot be turned off. */}
          <Switch checked disabled label="Send alerts to Telegram (always on)" onChange={() => {}} />
        </div>
        <div className={s.howRow}>
          <span>Warn if pace runs over</span>
          <Switch checked={warnOnPace} disabled={!settings.data} label="Warn if pace runs over" onChange={(v) => void change({ warnOnPace: v })} />
        </div>
      </div>
    </>
  );

  return (
    <AppShell home="limits" glyph="limits" title="Limits" description="A spending ceiling for each category. You get a warning before you reach it." aside={aside}>
      <div className="rise" style={{ flex: 'none' }}>
        <div className="lbl">{today ? daysLeftText(today.day, today.days, mName) : ' '}</div>
        <div className={s.headline}>{rows ? headline(rows, displayTag) : '—'}</div>
      </div>

      <div className={`mono ${s.legend}`}>
        <span><span className={s.sw} style={{ width: 18, height: 8, background: 'var(--track)' }} />the bar&rsquo;s full length is your limit</span>
        <span><span className={s.sw} style={{ width: 2, height: 14, background: 'var(--ink)' }} />your alert level ({level}%)</span>
        <span><span className={s.sw} style={{ width: 11, height: 11, background: 'var(--g-accent-h)' }} />within the limit</span>
        <span><span className={s.sw} style={{ width: 11, height: 11, background: 'var(--g-warn-h)' }} />close to it ({level}%+)</span>
        <span><span className={s.sw} style={{ width: 11, height: 11, background: 'var(--g-danger-h)' }} />over the limit</span>
      </div>

      <div className={s.rows}>
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
          rows.map((r) => <LimitItem key={r.id} row={r} month={month} mName={mName} onChanged={() => budgets.mutate()} />)
        )}
      </div>

      <div className={s.bottom}>
        <AddLimit month={month} mName={mName} known={(cats.data?.items ?? []).filter((c) => !c.archived).map((c) => c.name)} onAdded={() => { void budgets.mutate(); void cats.mutate(); }} />
        <section className="opt" aria-labelledby="warn-h">
          <h2 id="warn-h" className={s.h3}>Recent warnings</h2>
          <div className={s.warns}>
            {alerts.error && !alerts.data ? (
              <div style={{ padding: '7px 0' }}><ErrorLine>Could not load warnings.</ErrorLine><TextLink mono onClick={() => void alerts.mutate()}>Try again</TextLink></div>
            ) : !alerts.data ? (
              <Loading>loading…</Loading>
            ) : alerts.data.items.length === 0 ? (
              <div className={`${s.warn} cap`}>No warnings yet.</div>
            ) : (
              alerts.data.items.map((a) => (
                <div key={a.id} className={s.warn}>
                  <span className={`${s.d} mono lbl`}>{monthDay(a.sentAt, today?.tz)}</span>
                  <span className={s.t}>{warningText(a, budgets.data?.items ?? [], level, displayTag)}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function LimitItem({ row: r, month, mName, onChanged }: { row: LimitRow; month: string | undefined; mName: string; onChanged: () => unknown }) {
  const [mode, setMode] = useState<'edit' | 'remove' | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const name = displayTag(r.name);
  const over = r.status === 'over';

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
    <div className={s.limit} data-open={mode !== null}>
      <div className={s.top}>
        <div className={s.who}>
          <span className={s.nm}>{name}</span>
          <span className={s.stat}><span className={s.dot} data-k={r.status} aria-hidden="true" />{r.statusText}</span>
          <span className={s.acts}>
            <button type="button" className="link mono" aria-expanded={mode === 'edit'} aria-label={`Change the ${name} limit`} onClick={() => (mode === 'edit' ? setMode(null) : open('edit'))}>Change</button>
            <button type="button" className="link mono" aria-expanded={mode === 'remove'} aria-label={`Remove the ${name} limit`} onClick={() => (mode === 'remove' ? setMode(null) : open('remove'))}>Remove</button>
          </span>
        </div>
        <div>
          <span className={`fig-md ${s.left} ${over ? 'neg' : ''}`}>{inr(r.leftMinor)}</span>
          <span className={s.leftLbl}>{r.leftMinor >= 0 ? 'left to spend' : 'over'}</span>
        </div>
      </div>
      <div className={s.barWrap}>
        <ProgressBar size="l" ratio={r.ratio} colour={barFor(r.status)} tick={r.alertPct / 100} label={`${name}: ${r.pct}% of the limit spent, alert at ${r.alertPct}%`} />
      </div>
      <div className={s.cap2}>
        <span><b className="mono">{inr(r.spentMinor)}</b> of {inr(r.limitMinor)} spent · {r.pct}%</span>
        <span>
          At this pace you reach {inr(r.projectedMinor)} by month end,{' '}
          <b className={r.diffMinor > 0 ? 'neg' : ''}>{r.diffMinor > 0 ? `${inr(r.diffMinor)} over` : `${inr(-r.diffMinor)} under`}</b>
        </span>
      </div>

      {mode === 'edit' && (
        <div className={s.wellWrap}>
          <ConfirmWell text={`Change the monthly limit for ${name}. Raising it brings its warnings back for this month.`}>
            <div className={s.editFields}>
              <div className={s.amt}>
                <Field label="Monthly limit" inputMode="decimal" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void save(); }} />
              </div>
              <Button disabled={busy} onClick={() => void save()}>Save limit</Button>
              <TextLink mono onClick={() => void run(() => api.patch<BudgetDto>(`/budgets/${r.id}`, { useMonthAllocation: true, month }))}>Use {mName}&rsquo;s plan allocation</TextLink>
              <TextLink mono onClick={() => setMode(null)}>Cancel</TextLink>
            </div>
            {err && <ErrorLine>{err}</ErrorLine>}
          </ConfirmWell>
        </div>
      )}
      {mode === 'remove' && (
        <div className={s.wellWrap}>
          <ConfirmWell text={`Remove the ${name} limit and stop its warnings? Your payments and plan stay as they are. You can set a new limit any time.`}>
            <GhostButton bad disabled={busy} onClick={() => void run(() => api.del(`/budgets/${r.id}`))}>Remove limit</GhostButton>
            <TextLink mono onClick={() => setMode(null)}>Cancel</TextLink>
            {err && <ErrorLine>{err}</ErrorLine>}
          </ConfirmWell>
        </div>
      )}
    </div>
  );
}

function AddLimit({ month, mName, known, onAdded }: { month: string | undefined; mName: string; known: string[]; onAdded: () => void }) {
  const [cat, setCat] = useState('');
  const [amt, setAmt] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function submit(useAllocation: boolean) {
    setErr('');
    const tag = cat.trim();
    if (!tag) { setErr('Type a category or tag.'); return; }
    let body: Record<string, unknown>;
    if (useAllocation) body = { tag, useMonthAllocation: true, month };
    else {
      const p = parseAmount(amt);
      if (p === null) { setErr('Enter a monthly limit like ₹2,000.'); return; }
      body = { tag, limitMinor: p };
    }
    setBusy(true);
    try { await api.post('/budgets', body); setCat(''); setAmt(''); onAdded(); } catch (e) { setErr(Object.values(fieldErrors(e))[0] ?? errorText(e)); } finally { setBusy(false); }
  }

  return (
    <section aria-labelledby="add-h">
      <h2 id="add-h" className={s.h3}>Add a limit</h2>
      <form className={s.form} onSubmit={(e) => { e.preventDefault(); void submit(false); }}>
        <div className={s.formCat}><Field label="Category or tag" placeholder="#tag" list="limit-cats" autoComplete="off" value={cat} onChange={(e) => setCat(e.target.value)} /></div>
        <div className={s.formAmt}><Field label="Monthly limit" inputMode="decimal" autoComplete="off" value={amt} onChange={(e) => setAmt(e.target.value)} /></div>
        <Button type="submit" className={s.formBtn} disabled={busy}>Set limit</Button>
        <datalist id="limit-cats">{known.map((n) => <option key={n} value={n} />)}</datalist>
      </form>
      <div className={s.formNote}>
        {err && <ErrorLine>{err}</ErrorLine>}
        <TextLink mono onClick={() => void submit(true)}>Use {mName}&rsquo;s plan allocation as the limit</TextLink>
      </div>
    </section>
  );
}
