'use client';
import { useEffect, useRef, useState } from 'react';
import type { z } from 'zod';
import { displayTag, figure, inr, plain } from '@/common';
import type { BudgetsRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { Button, Empty, ErrorLine, Loading, ProgressBar, SectionTabs, StatusLine, Stepper, TextLink } from '@/components/ui';
import { api, errorText, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { addTag, type Draft, draftFrom, forecastLink, groupLines, lineView, monthName, nextMonthName, paceMinor, type Placed, planMath, type PlanResponse, RAMP, segments, stepLine, stepTotal, suggestions, toPutBody } from '@/features/plan';
import type { RecurringList } from '@/features/repeats';
import s from './page.module.css';

type Save = 'idle' | 'saving' | 'saved' | 'error';
const SAVE_DELAY = 700;

export default function PlanPage() {
  const today = useToday();
  const month = today?.month;
  const path = month ? `/plans/${month}` : null;
  const { data, error, mutate } = useApi<PlanResponse>(path);
  const { data: cats } = useApi<{ items: { name: string; archived: boolean }[] }>(month ? '/categories' : null);
  const budgets = useApi<z.infer<typeof BudgetsRes>>(month ? `/budgets?month=${month}` : null);
  // categories of your repeats (Rent, SIP) are fixed: they end the month where they were planned
  const repeats = useApi<RecurringList>(month ? '/recurring' : null);
  const fixed = new Set((repeats.data?.items ?? []).map((r) => r.categoryId));

  const [draft, setDraft] = useState<Draft | null>(null);
  const [save, setSave] = useState<Save>('idle');
  const [saveError, setSaveError] = useState('');
  const [tag, setTag] = useState('');
  const [tagError, setTagError] = useState('');

  // The draft is what the person sees; it is saved a moment after the last change (or at once for a new category).
  const draftRef = useRef<Draft | null>(null);
  const dirty = useRef(false);
  const version = useRef(0);
  const inflight = useRef(false);
  const again = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pathRef = useRef(path);
  pathRef.current = path;

  useEffect(() => {
    if (data && !dirty.current) { const d = draftFrom(data); draftRef.current = d; setDraft(d); }
  }, [data]);

  async function flush(): Promise<void> {
    const d = draftRef.current;
    const p = pathRef.current;
    if (!d || !p) return;
    if (inflight.current) { again.current = true; return; } // two PUTs must not cross: run one after the other
    inflight.current = true;
    const v = version.current;
    setSave('saving');
    try {
      const res = await api.put<PlanResponse>(p, toPutBody(d));
      if (v === version.current) { dirty.current = false; const nd = draftFrom(res); draftRef.current = nd; setDraft(nd); }
      await mutate(res, { revalidate: false });
      setSave('saved');
    } catch (e) {
      setSave('error');
      setSaveError(errorText(e, 'Could not save the plan. Your changes are kept. Try again.'));
    } finally {
      inflight.current = false;
      if (again.current) { again.current = false; void flush(); }
    }
  }
  const flushRef = useRef(flush);
  flushRef.current = flush;
  useEffect(() => () => { clearTimeout(timer.current); if (dirty.current) void flushRef.current(); }, []);

  function apply(next: Draft, now = false) {
    draftRef.current = next;
    dirty.current = true;
    version.current += 1;
    setDraft(next);
    setSave('idle');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => void flushRef.current(), now ? 0 : SAVE_DELAY);
  }
  function discard() {
    clearTimeout(timer.current);
    dirty.current = false;
    setSave('idle');
    if (data) { const d = draftFrom(data); draftRef.current = d; setDraft(d); }
  }
  function create(raw: string) {
    if (!draft) return;
    const r = addTag(draft, raw);
    if (!r.ok) { setTagError(r.message); return; }
    setTagError('');
    setTag('');
    if (r.added) apply(r.draft, true);
  }

  const math = draft ? planMath(draft) : null;
  const seg = draft ? segments(draft) : null;
  const groups = draft ? groupLines(draft, fixed) : null;
  const mName = month ? monthName(month) : 'this month';
  const pace = (l: Placed['line']) => paceMinor(l, l.categoryId !== undefined && fixed.has(l.categoryId), today?.day ?? 0, today?.days ?? 0);
  const ideas = draft ? suggestions(draft, (cats?.items ?? []).filter((c) => !c.archived).map((c) => c.name)) : [];

  const aside = (
    <>
      <div className="math mono" style={{ marginTop: 28 }}>
        <div className={`r ${s.totalRow}`}>
          <span className="k">to plan</span>
          <span className={s.ctl}>
            <Stepper glyph="−" label="Decrease total by 5,000" disabled={!draft} onClick={() => draft && apply(stepTotal(draft, -1))} />
            <span className={s.stepVal}>{draft ? plain(draft.totalMinor) : '—'}</span>
            <Stepper glyph="+" label="Increase total by 5,000" disabled={!draft} onClick={() => draft && apply(stepTotal(draft, 1))} />
          </span>
        </div>
        <div className="r"><span className="k">− assigned</span><span>{math ? plain(math.assigned) : '—'}</span></div>
        <div className="r total">
          <span className="k" style={{ color: 'inherit' }}>{math?.over ? '= over-assigned' : '= unassigned'}</span>
          <span className={math?.over ? 'neg' : 'v'}>{math ? figure(math.unassigned) : '—'}</span>
        </div>
      </div>
      <div className={`opt2 cap ${s.note}`}>Unspent money carries into {month ? nextMonthName(month) : 'next month'}. Over-assigning is allowed, but flagged.</div>
    </>
  );

  function row({ line: l, index: i }: Placed, editable: boolean) {
    if (!draft) return null;
    const v = lineView(l);
    const name = displayTag(l.name);
    return (
      <div key={l.name} className={`row ${s.prow}`} role="row">
        <div className={`${s.cCat} ${s.name}`} role="cell">
          <span aria-hidden="true" className={s.swatch} style={{ background: RAMP[i % RAMP.length] }} />
          <span className="row-title">{name}</span>
        </div>
        <div className={`${s.cPlanned} ${s.planned}`} role="cell">
          {editable ? (
            <>
              <Stepper glyph="−" label={`Decrease ${name} by 500`} disabled={l.allocatedMinor <= 0} onClick={() => apply(stepLine(draft, i, -1))} />
              <span className={s.planVal}>{plain(l.allocatedMinor)}</span>
              <Stepper glyph="+" label={`Increase ${name} by 500`} onClick={() => apply(stepLine(draft, i, 1))} />
            </>
          ) : <span className={`${s.planVal} ${s.fixedVal}`}>{plain(l.allocatedMinor)}</span>}
        </div>
        <div className={`${s.cSpent} mono`} role="cell">{plain(l.spentMinor)}</div>
        <div className={`${s.cLeft} mono ${v.over ? 'neg' : ''}`} role="cell">{figure(v.remainMinor)}</div>
        <div className={s.cUsed} role="cell">
          <ProgressBar ratio={v.pct / 100} colour={v.colour} label={`${name}: ${Math.round(v.pct)}% of the plan used`} />
        </div>
        <div className={`${s.cPace} mono ${pace(l) > l.allocatedMinor ? 'neg' : ''}`} role="cell">
          {today ? `${plain(pace(l))}${pace(l) > l.allocatedMinor ? ' ▲' : ''}` : '—'}
        </div>
      </div>
    );
  }

  return (
    <AppShell home="budget" glyph="budget" title="Budget" description={`Give every rupee of ${mName} a job, then guard the categories that run hot.`} aside={aside}>
      <SectionTabs
        label="Budget"
        hint="Step 1 of 2. Split the month. Step 2 puts a limit on the risky ones."
        tabs={[
          { href: '/budget', label: 'Plan', count: draft?.lines.length, active: true },
          { href: '/budget/limits', label: 'Limits', count: budgets.data?.items.filter((b) => b.active).length, active: false },
        ]}
      />
      <div className="sechead">
        <h2 className="h2">How {mName} is split</h2>
        <div className="lbl" style={{ textTransform: 'none' }}>green is money not yet given a job</div>
      </div>

      {error && !draft ? (
        <div style={{ padding: '12px 0' }}>
          <ErrorLine>{errorText(error, 'Could not load your plan.')}</ErrorLine>
          <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void mutate()}>Try again</TextLink></div>
        </div>
      ) : !draft || !math || !seg || !groups ? (
        <Loading>loading…</Loading>
      ) : (
        <>
          <div
            className={s.split} role="img"
            aria-label={`${inr(math.assigned)} of ${inr(draft.totalMinor)} given a job: ${draft.lines.map((l) => `${displayTag(l.name)} ${inr(l.allocatedMinor)}`).join(', ') || 'nothing yet'}`}
          >
            {draft.lines.map((l, i) => <span key={l.name} style={{ width: `${seg.widths[i]!.toFixed(2)}%`, background: RAMP[i % RAMP.length] }} />)}
            <span style={{ width: `${seg.free.toFixed(2)}%`, background: 'var(--accent-pale)' }} />
          </div>

          <div className={s.tableWrap}>
            <div className={s.tableInner} role="table" aria-label={`${mName} plan by category`}>
              <div className={`${s.thead} th-row lbl`} role="row">
                <div className={s.cCat} role="columnheader">Category</div>
                <div className={s.cPlanned} role="columnheader">Planned</div>
                <div className={s.cSpent} role="columnheader">Spent</div>
                <div className={s.cLeft} role="columnheader">Left</div>
                <div className={s.cUsed} role="columnheader">Used</div>
                <div className={s.cPace} role="columnheader">At this pace</div>
              </div>
              {draft.lines.length === 0 && <Empty>Nothing planned yet. Type a tag to create your first category.</Empty>}
              {groups.flexible.length > 0 && (
                <div role="rowgroup" aria-label="Flexible">
                  <div className={s.grp}><span className="lbl">Flexible</span><span className="lbl mono">{plain(groups.flexibleMinor)}</span></div>
                  {groups.flexible.map((p) => row(p, true))}
                </div>
              )}
              {groups.fixed.length > 0 && (
                <div role="rowgroup" aria-label="Fixed">
                  <div className={s.grp}><span className="lbl">Fixed · set by your repeats</span><span className="lbl mono">{plain(groups.fixedMinor)}</span></div>
                  {groups.fixed.map((p) => row(p, false))}
                </div>
              )}
            </div>
          </div>

          <div className={s.saveline}>
            <div className={s.status}>
              {save === 'saving' && <StatusLine kind="wait">Saving…</StatusLine>}
              {save === 'saved' && <StatusLine>Saved</StatusLine>}
              {save === 'error' && (
                <>
                  <ErrorLine>{saveError}</ErrorLine>
                  <TextLink mono onClick={() => void flush()}>Try again</TextLink>
                  <TextLink mono onClick={discard}>Discard changes</TextLink>
                </>
              )}
            </div>
            <TextLink mono href="/forecast">{month && today ? forecastLink(groups, month, today.day, today.days) : 'see the Forecast →'}</TextLink>
          </div>
        </>
      )}

      <form className="formrow" onSubmit={(e) => { e.preventDefault(); create(tag); }}>
        <div className="fld">
          <label htmlFor="new-tag" className="lbl">New category · just type a tag</label>
          <input id="new-tag" className={`boxin ${s.tagIn}`} type="text" placeholder="#tag" value={tag} autoComplete="off" disabled={!draft} aria-invalid={Boolean(tagError)} onChange={(e) => { setTag(e.target.value); setTagError(''); }} />
        </div>
        <Button type="submit" disabled={!draft || !tag.trim()}>Create</Button>
        <span className={s.suggest}>
          {ideas.map((n) => <button key={n} type="button" className="link mono" onClick={() => create(n)}>+ #{n}</button>)}
        </span>
      </form>
      {tagError && <ErrorLine>{tagError}</ErrorLine>}
    </AppShell>
  );
}
