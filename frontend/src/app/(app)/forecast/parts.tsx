import type { ReactNode } from 'react';
import Link from 'next/link';
import { inr, type LeadPart, monthName, shortMonth } from '@/common';
import { AppShell } from '@/components/shell';
import { ErrorLine, Loading, SectionTabs, TextLink } from '@/components/ui';
import { endStat, runOutStat } from '@/features/forecast';
import type { Model } from './use-forecast';
import s from './page.module.css';

type Tab = 'month' | 'categories' | 'history';

/** Shell, aside figures and the three tabs shared by every Forecast page. `hint` is the one line beside the tabs. */
export function ForecastFrame({ active, model, month, hint, children }: { active: Tab; model: Model | null; month: string | null; hint: string; children: ReactNode }) {
  const tabs: { key: Tab; href: string; label: string; count?: number }[] = [
    { key: 'month', href: '/forecast', label: 'This month' },
    { key: 'categories', href: '/forecast/categories', label: 'Categories', count: model?.rows.length },
    { key: 'history', href: '/forecast/history', label: 'Six months' },
  ];
  return (
    <AppShell
      home="forecast" glyph="forecast" title="Forecast"
      description={`Where ${month ? monthName(month) : 'this month'} is heading.`}
      aside={<Aside model={model} month={month} />}
    >
      <SectionTabs label="Forecast" hint={hint} tabs={tabs.map((t) => ({ ...t, active: t.key === active }))} />
      <div className={s.sections}>{children}</div>
    </AppShell>
  );
}

function Aside({ model, month }: { model: Model | null; month: string | null }) {
  const live = model && !model.f.empty;
  const run = live && month ? runOutStat(model.f, month) : null;
  const end = live ? endStat(model.f) : null;
  const safe = model?.f.safePerDayMinor;
  const stats = [
    { label: 'Plan runs out', value: run ? run.value : '—', note: run ? run.note : ' ', bad: run?.tone === 'bad' },
    { label: month && model ? `Left on ${shortMonth(month)} ${model.input.daysInMonth}` : 'Left at month end', value: end ? end.value : '—', note: end ? end.note : ' ', bad: false },
    { label: 'Safe to spend a day', value: live && safe !== null && safe !== undefined ? inr(safe) : '—', note: live ? `you spend ${inr(model.f.spendingNowMinor)}` : ' ', bad: false },
  ];
  return (
    <div className={s.stats}>
      {stats.map((st) => (
        <div key={st.label} className={s.stat}>
          <div className="lbl">{st.label}</div>
          <div className={`${s.statFig} ${st.bad ? 'neg' : ''}`}>{st.value}</div>
          <div className={`mono ${s.statNote}`}>{st.note}</div>
        </div>
      ))}
    </div>
  );
}

/** The sentence at the top of a tab; figures are bold, and red when `bad`. */
export function Lead({ parts }: { parts: LeadPart[] }) {
  return (
    <section className={s.section} aria-label="Summary">
      <p className="lead">
        {parts.map((p, i) => (typeof p === 'string' ? p : <b key={i} className={`${s.fig} ${p.bad ? s.figBad : ''}`}>{p.b}</b>))}
      </p>
    </section>
  );
}

type PagerSide = { href: string; label: string } | { text: string };

/** The line under a tab: where to go next, and where you came from. */
export function Pager({ left, right }: { left: PagerSide; right: { href: string; label: string } }) {
  return (
    <nav className={s.pager} aria-label="Forecast steps">
      {'href' in left ? <Link className={`mono ${s.go}`} href={left.href}>{left.label}</Link> : <span className="cap">{left.text}</span>}
      <Link className={`mono ${s.go}`} href={right.href}>{right.label}</Link>
    </nav>
  );
}

/** Loading, or the failed request with a retry, while the model is not ready. */
export function Pending({ error, retry }: { error: string | null; retry: () => void }) {
  return error ? (
    <div style={{ padding: '12px 0' }}>
      <ErrorLine>{error}</ErrorLine>
      <div style={{ marginTop: 8 }}><TextLink mono onClick={retry}>Try again</TextLink></div>
    </div>
  ) : <Loading />;
}
