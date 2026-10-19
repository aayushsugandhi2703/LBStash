'use client';
import { type CSSProperties, useEffect, useState } from 'react';
import type { DashboardRes, ReportDailyRes } from '@/contracts';
import { figure, formatInr, inr, monthName, shortMonth } from '@/common';
import { AppShell } from '@/components/shell';
import { Empty, ErrorLine, LedgerMath, Loading, Segmented, StripLink, TextLink, Tip } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { dayChart, degradedNote, flowGeometry, flowLabel, flowRows, heroSentence, leftStack, nowLinks } from '@/features/now';
import s from './page.module.css';

type View = 'flow' | 'days';

export default function NowPage() {
  const dash = useApi<DashboardRes>('/dashboard');
  const [view, setView] = useState<View>('flow');
  const d = dash.data;
  const month = d ? monthName(d.month) : null;

  return (
    <AppShell
      home="now" glyph="now" title="Now"
      description={`Where you stand today, and where ${month ? `${month}'s` : 'this month’s'} money went.`}
      aside={d && <Aside d={d} />}
    >
      <Hero d={d} loading={dash.isLoading} error={dash.error ? errorText(dash.error, 'Could not load this page. Try again.') : null} retry={() => void dash.mutate()} />
      {d && <Links d={d} />}
      <section className={s.panel} aria-label={view === 'flow' ? 'Where it went' : 'Day by day'}>
        <div className={s.panelHead}>
          <h2 className="h2">{view === 'flow' ? 'Where it went' : 'Day by day'}</h2>
          <Segmented<View> label="View" value={view} onChange={setView} options={[{ value: 'flow', label: 'Flow' }, { value: 'days', label: 'Day by day' }]} />
        </div>
        {view === 'flow' ? <FlowView d={d} loading={dash.isLoading} /> : <DayView />}
      </section>
    </AppShell>
  );
}

function Aside({ d }: { d: DashboardRes }) {
  const b = d.balance;
  return (
    <>
      <div className={s.mathA}>
        <LedgerMath
          rows={[
            { k: 'carried over', v: figure(b.carriedOver), tone: 'credit' },
            { k: '+ income', v: figure(b.income), tone: 'credit' },
            { k: '− spent', v: figure(b.spent), tone: 'debit' },
          ]}
          total={{ k: '= available', v: <span className={s.ink}>{figure(b.available)}</span> }}
        />
      </div>
      <div className={`${s.mathB} opt2`}>
        <LedgerMath
          rows={[{ k: 'plan left', v: figure(d.safeToSpend.planLeft) }, { k: '÷ days left', v: d.safeToSpend.daysLeft }]}
          total={{ k: '= per day', v: figure(d.safeToSpend.perDay) }}
        />
      </div>
    </>
  );
}

function Hero({ d, loading, error, retry }: { d?: DashboardRes; loading: boolean; error: string | null; retry: () => void }) {
  const sentence = d ? heroSentence(d) : null;
  const neg = d ? d.balance.available < 0 : false;
  return (
    <div className={`rise ${s.hero}`}>
      <div className="lbl">Available to you</div>
      <div className={`display ${s.heroNumber}`} aria-live="polite">
        {d ? (
          <>{neg && '−'}<span className="rs" style={{ marginRight: 6 }}>₹</span>{formatInr(Math.abs(d.balance.available))}</>
        ) : '—'}
      </div>
      {sentence && (
        <p className={`lead ${s.sentence}`}>
          {sentence.before}{sentence.em && <em>{sentence.em}</em>}{sentence.after}
        </p>
      )}
      {!d && loading && <Loading />}
      {!d && error && (
        <div style={{ marginTop: 12 }}>
          <ErrorLine>{error}</ErrorLine>
          <div style={{ marginTop: 8 }}><TextLink onClick={retry}>Try again</TextLink></div>
        </div>
      )}
    </div>
  );
}

function Links({ d }: { d: DashboardRes }) {
  const links = nowLinks(d.attention);
  const note = degradedNote(d.degraded);
  return (
    <>
      <div className={`strip ${s.links}`}>
        {links.map((l) => (
          <StripLink key={l.key} tag={l.tag} href={l.href}>
            {l.marker && <span className={s.marker} data-k={l.marker} aria-hidden="true" />}
            {l.text}
          </StripLink>
        ))}
      </div>
      {note && <p className={`cap ${s.degraded}`} role="status">{note}</p>}
    </>
  );
}

function FlowView({ d, loading }: { d?: DashboardRes; loading: boolean }) {
  if (!d) return loading ? <Loading /> : null;
  const rows = flowRows(d.flow);
  const g = flowGeometry(rows);
  if (g.total === 0) return <Empty>Where your money went appears here once you log payments in Telegram.</Empty>;
  const left = leftStack(d.balance.carriedOver, d.balance.income);
  return (
    <div className={s.flowWrap}>
      <div className={s.flow}>
        <div className={s.lcol}>
          {left.map((l) => (
            <div key={l.kind} className={s.llabel} style={{ top: `${l.centrePct}%` }}>
              <div className={s.name}>{l.name}</div>
              <div className={`mono ${s.amt}`}>{l.amount}</div>
            </div>
          ))}
        </div>
        <div className={s.lnodes}>
          {left.length === 0 ? <div style={{ flex: 1, background: '#9A9AA6' }} /> : left.map((l) => (
            <div key={l.kind} style={{ flex: `${l.flex} 1 0`, ...(l.kind === 'carried' ? { background: '#9A9AA6' } : { background: 'var(--ink)', borderTop: '2px solid #fff', boxSizing: 'border-box' }) }} />
          ))}
        </div>
        <div className={s.ribbons}>
          <svg viewBox="0 0 100 330" preserveAspectRatio="none" role="img" aria-label={flowLabel(g.total, d.balance.available)}>
            {g.ribbons.map((r) => <path key={r.title} className={r.av ? s.ribAv : s.rib} d={r.d}><title>{r.title}</title></path>)}
          </svg>
        </div>
        <div className={s.rnodes} aria-hidden="true">
          {g.nodes.map((n) => <div key={n.name} className={s.rnode} data-av={n.av} style={{ top: `${n.topPct}%`, height: `max(2px, ${n.heightPct}%)` }} />)}
        </div>
        <div className={s.rlabels}>
          {g.nodes.map((n) => (
            <div key={n.name} className={s.rlabel} data-av={n.av} style={{ top: `calc(${n.labelTopPct}% - 10px)` }}>
              <span className={s.name}>{n.name}</span><span className={`mono ${s.amt}`}>{n.amount}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const tipStyle = (side: 'centre' | 'end'): CSSProperties =>
  side === 'end' ? { right: 0, top: -8, transform: 'translateY(-100%)' } : { left: '50%', top: -8, transform: 'translate(-50%,-100%)' };

function DayView() {
  const daily = useApi<ReportDailyRes>('/reports/daily');
  // Keep showing the last chart while a refetch runs (design system §10: previous render at reduced opacity).
  const [last, setLast] = useState<ReportDailyRes>();
  useEffect(() => { if (daily.data) setLast(daily.data); }, [daily.data]);
  const data = daily.data ?? last;
  if (!data) {
    if (daily.error) return <div style={{ marginTop: 14 }}><ErrorLine>{errorText(daily.error, 'Could not load the days. Try again.')}</ErrorLine><div style={{ marginTop: 8 }}><TextLink onClick={() => void daily.mutate()}>Try again</TextLink></div></div>;
    return <Loading />;
  }
  const c = dayChart(data);
  const mon = shortMonth(data.month);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }} className={daily.isValidating && !daily.data ? s.stale : undefined}>
      <div
        className={s.plot} role="group"
        aria-label={`Spending per day in ${monthName(data.month)}, rent and fixed payments left out: ${inr(data.totalMinor)} over ${data.dayOfMonth} days${c.avgTopPct === null ? '' : `, average ${c.legend.replace(/^average /, '').split(' · ')[0]}`}`}
      >
        <div className={s.grid} style={{ top: 0 }}><span className="mono">{formatInr(c.scale.max)}</span></div>
        <div className={s.grid} style={{ top: '50%' }}><span className="mono">{formatInr(c.scale.mid)}</span></div>
        <div className={s.grid} data-base="true" style={{ top: '100%' }}><span className="mono">0</span></div>
        {c.avgTopPct !== null && <div className={s.avg} style={{ top: `${c.avgTopPct}%` }} />}
        <div className={s.cols}>
          {c.days.map((day, i) => (
            <button key={day.day} type="button" className={`${s.col} ${day.future ? '' : 'has-tip'}`} aria-label={day.future ? `${mon} ${day.day}, not yet` : day.tip}>
              {day.future
                ? <span className={s.stub} />
                : <span className={`vbar ${s.bar}`} data-c="ink" style={{ height: `${day.heightPct}%`, animationDelay: `${((i + 1) * 0.02).toFixed(2)}s` }} />}
              {day.axis && <span className={`mono ${s.axis}`}>{day.axis}</span>}
              {!day.future && <Tip title={day.tip} style={tipStyle(day.tipSide)} />}
            </button>
          ))}
        </div>
      </div>
      <div className={`mono ${s.legend}`}>{c.avgTopPct !== null && <i aria-hidden="true" />}{c.legend}</div>
    </div>
  );
}
