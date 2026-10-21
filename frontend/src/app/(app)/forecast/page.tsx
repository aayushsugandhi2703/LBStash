'use client';
import { useMemo } from 'react';
import type { z } from 'zod';
import type { BudgetsRes, DashboardRes, RecurringRes, ReportDailyRes, ReportMatrixRes, ReportMonthsRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { Empty, ErrorLine, Loading, TextLink } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { inr, inrSigned, monthName, plain, shortMonth } from '@/common';
import {
  categoryRows, CHART, endStat, flexibleLines, forecast, forecastChart, forecastInput, limitsById, repeatsLeft, runOutStat, verdictText,
  type CategoryRow, type Forecast, type ForecastChart, type RepeatLeft,
} from '@/features/forecast';
import type { PlanResponse } from '@/features/plan';
import { headline, trendsChart, usualRows } from '@/features/trends';
import { MonthChart } from './month-chart';
import s from './page.module.css';

const RANGE = 6;
type Budgets = z.infer<typeof BudgetsRes>;
type Recurring = z.infer<typeof RecurringRes>;

export default function ForecastPage() {
  const today = useToday();
  const daily = useApi<ReportDailyRes>('/reports/daily');
  const month = daily.data?.month ?? today?.month ?? null;
  const plan = useApi<PlanResponse>(month ? `/plans/${month}` : null);
  const budgets = useApi<Budgets>(month ? `/budgets?month=${month}` : null);
  const recurring = useApi<Recurring>('/recurring');
  const dash = useApi<DashboardRes>('/dashboard');

  const model = useMemo(
    () => buildModel(daily.data, plan.data, budgets.data, recurring.data, dash.data, today?.today),
    [daily.data, plan.data, budgets.data, recurring.data, dash.data, today?.today],
  );

  const error = daily.error ?? plan.error ?? budgets.error ?? recurring.error ?? dash.error;
  const retry = () => { void daily.mutate(); void plan.mutate(); void budgets.mutate(); void recurring.mutate(); void dash.mutate(); };

  return (
    <AppShell
      home="forecast" glyph="forecast" title="Forecast"
      description="Where this month is heading if you keep spending like this."
      aside={<Aside model={model} month={month} />}
    >
      <div className={s.sections}>
        {model ? (
          <>
            <Summary month={model.input.month} day={model.input.dayOfMonth} days={model.input.daysInMonth} text={model.f.headline} />
            {!model.f.empty && (
              <>
                <ChartSection f={model.f} chart={model.chart} hasPlan={model.input.planFlexMinor > 0} />
                {model.f.daysLeft > 0 && <EndsTable f={model.f} month={model.input.month} days={model.input.daysInMonth} left={model.left.items} spentSoFar={model.input.spentSoFarMinor} />}
                {model.rows.length > 0 && <Categories rows={model.rows} month={model.input.month} />}
              </>
            )}
          </>
        ) : error ? (
          <div style={{ padding: '12px 0' }}>
            <ErrorLine>{errorText(error, 'Could not load the forecast.')}</ErrorLine>
            <div style={{ marginTop: 8 }}><TextLink mono onClick={retry}>Try again</TextLink></div>
          </div>
        ) : <Loading />}
        <History />
      </div>
    </AppShell>
  );
}

/** Everything the page shows, once all five endpoints have answered. */
function buildModel(
  d: ReportDailyRes | undefined, plan: PlanResponse | undefined, budgets: Budgets | undefined, recurring: Recurring | undefined,
  dash: DashboardRes | undefined, today: string | undefined,
) {
  if (!d || !plan || !budgets || !recurring || !dash || !today) return null;
  const left = repeatsLeft(recurring.items, today, d.daysInMonth - d.dayOfMonth);
  const input = forecastInput({ daily: d, planLines: plan.lines, spentSoFarMinor: dash.balance.spent, availableMinor: dash.balance.available, repeatsLeftMinor: left.totalMinor });
  const f = forecast(input);
  const rows = categoryRows(flexibleLines(plan.lines, d.fixedCategories), limitsById(budgets.items), d.dayOfMonth, d.daysInMonth);
  return { input, f, left, rows, chart: forecastChart(input, f) };
}
type Model = NonNullable<ReturnType<typeof buildModel>>;

function Aside({ model, month }: { model: Model | null; month: string | null }) {
  const run = model && month ? runOutStat(model.f, month) : null;
  const end = model && !model.f.empty ? endStat(model.f) : null;
  const safe = model?.f.safePerDayMinor;
  const stats = [
    { label: 'Plan runs out', value: run && !model?.f.empty ? run.value : '—', note: run && !model?.f.empty ? run.note : ' ', bad: run?.tone === 'bad' },
    { label: 'Month ends with', value: end ? end.value : '—', note: end ? end.note : ' ', bad: false },
    {
      label: 'Safe a day, flexible only', value: model && safe !== null && safe !== undefined && !model.f.empty ? inr(safe) : '—',
      note: model && !model.f.empty ? `you are spending ${inr(model.f.spendingNowMinor)}` : ' ', bad: false,
    },
  ];
  return (
    <>
      <div className={s.stats}>
        {stats.map((st) => (
          <div key={st.label} className={s.stat}>
            <div className="lbl">{st.label}</div>
            <div className={`${s.statFig} ${st.bad ? 'neg' : ''}`}>{st.value}</div>
            <div className={`mono ${s.statNote}`}>{st.note}</div>
          </div>
        ))}
      </div>
      <p className={`cap opt2 ${s.how}`}>Flexible spending so far ÷ days gone, carried to the month end. Repeats are added on their due dates, not spread across the days.</p>
    </>
  );
}

function Summary({ month, day, days, text }: { month: string; day: number; days: number; text: string }) {
  return (
    <section className={s.section} aria-label="Summary">
      <div className="lbl">{monthName(month)} · day {day} of {days}</div>
      <p className={`lead ${s.sentence}`}>{text}</p>
    </section>
  );
}

function ChartSection({ f, chart, hasPlan }: { f: Forecast; chart: ForecastChart; hasPlan: boolean }) {
  return (
    <section className={s.section} aria-label="Flexible spending this month">
      <div className={s.head}>
        <h2 className="h2">Flexible spending this month</h2>
        <span className="lbl" style={{ textTransform: 'none' }}>running total, without repeats</span>
      </div>
      <div className={s.legend}>
        <span><i />so far</span>
        {f.daysLeft > 0 && <span><i data-k="dash" />at this month’s pace</span>}
        {f.hasRange && <span><i data-k="range" />range: {f.low.label.toLowerCase()} to {f.high.label.toLowerCase()}</span>}
        {hasPlan && <span><i data-k="plan" />plan</span>}
      </div>
      <div className={s.chartBox}><Chart chart={chart} /></div>
    </section>
  );
}

function Chart({ chart: c }: { chart: ForecastChart }) {
  const { left, right, top, bottom, width, height } = CHART;
  return (
    <svg className={s.svg} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={c.summary}>
      {c.yTicks.slice(1).map((t) => <path key={t.label} className={s.gridline} d={`M${left} ${t.y.toFixed(1)} H${right}`} />)}
      <path className={s.axis} d={`M${left} ${bottom} H${right}`} />
      {c.yTicks.map((t) => <text key={t.label} className={`${s.t} ${s.tEnd}`} x={left - 8} y={t.y + 4}>{t.label}</text>)}
      {c.band && <path className={s.band} d={c.band} />}
      {c.planY !== null && <path className={s.plan} d={`M${left} ${c.planY.toFixed(1)} H${right}`} />}
      <path className={s.todayLine} d={`M${c.todayX.toFixed(1)} ${top} V${bottom}`} />
      {c.high && <path className={s.edge} d={c.high} />}
      {c.low && <path className={s.edge} d={c.low} />}
      {c.expected && <path className={s.expected} d={c.expected} />}
      <path className={s.actual} d={c.actual} />
      <circle className={s.dotToday} cx={c.todayX} cy={c.todayY} r="4.5" />
      {c.early && <circle className={s.dotEarly} cx={c.early.x} cy={c.early.y} r="4" />}
      {c.runOut && (
        <>
          <path className={s.leader} d={`M${c.runOut.x.toFixed(1)} ${(c.runOut.y + 6).toFixed(1)} V${(c.runOut.y + 33).toFixed(1)}`} />
          <circle className={s.dotRun} cx={c.runOut.x} cy={c.runOut.y} r="5" />
        </>
      )}
      <text className={`${s.t} ${s.tText} ${s.tEnd}`} x={c.todayX - 6} y={top + 14}>{c.todayLabel}</text>
      {c.planY !== null && <text className={`${s.t} ${s.tPlan}`} x={left + 4} y={c.planY - 7}>plan</text>}
      {c.runOut && <text className={`${s.t} ${s.tBad} ${s.tEnd}`} x={c.runOut.x + 5} y={c.runOut.y + 47}>{c.runOut.label}</text>}
      {c.early && <text className={`${s.t} ${s.tEnd}`} x={c.early.x - 8} y={c.early.y - 11}>{c.early.label}</text>}
      {c.ends.map((e) => <text key={e.label} className={`${s.t} ${e.strong ? `${s.tInk} ${s.tStrong}` : ''}`} x={right + 8} y={e.y + 4}>{e.label}</text>)}
      {c.xTicks.map((t) => <text key={t.x} className={`${s.t} ${s.tMid} ${t.today ? `${s.tPlan} ${s.tStrong}` : ''}`} x={t.x} y={bottom + 20}>{t.label}</text>)}
    </svg>
  );
}

const RUN_TEXT = (f: Forecast['scenarios'][number]): string => {
  const r = f.runOut;
  return r.kind === 'day' ? `plan runs out day ${r.day}` : '';
};

function EndsTable({ f, month, days, left, spentSoFar }: { f: Forecast; month: string; days: number; left: RepeatLeft[]; spentSoFar: number }) {
  const daysLeft = f.daysLeft;
  const names = [...new Set(left.map((i) => i.name))];
  const repeats = names.length === 0 ? '' : names.length <= 3 ? names.join(', ') : `${names.slice(0, 2).join(', ')} and ${names.length - 2} more`;
  const repeatsTotal = left.reduce((t, i) => t + i.amountMinor, 0);
  const cols = f.scenarios;
  return (
    <section className={s.section} aria-label={`How ${monthName(month)} ends`}>
      <div className={s.head}>
        <h2 className="h2">How {monthName(month)} ends</h2>
        <span className="lbl" style={{ textTransform: 'none' }}>three paces, the same repeats</span>
      </div>
      <div className={s.tableWrap}>
        <table className={s.table}>
          <thead>
            <tr className="lbl">
              <th scope="col"><span className="sr">Pace</span></th>
              {cols.map((c) => <th key={c.key} scope="col">{c.label}<br />{inr(Math.round(c.ratePerDay / 100) * 100)} a day</th>)}
            </tr>
          </thead>
          <tbody>
            <Row label="Already spent" cells={cols.map(() => plain(spentSoFar))} cols={cols} />
            <Row label={`+ flexible, next ${daysLeft} ${daysLeft === 1 ? 'day' : 'days'}`} cells={cols.map((c) => plain(c.flexLeftMinor))} cols={cols} />
            <Row label="+ repeats still to leave" hint={repeats ? `(${repeats})` : ''} cells={cols.map(() => plain(repeatsTotal))} cols={cols} />
            <Row label={`= spent in ${monthName(month)}`} cells={cols.map((c) => plain(c.spentEndMinor))} cols={cols} />
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" style={{ fontWeight: 500 }}>Balance on {shortMonth(month)} {days}</th>
              {cols.map((c) => <td key={c.key} className={`mono ${s.big} ${c.key === 'month' ? s.mid : ''}`}>{inrSigned(c.balanceEndMinor).replace('₹', '')}</td>)}
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="sr">{cols.map((c) => `${c.label}: ${RUN_TEXT(c)}`).filter((t) => !t.endsWith(': ')).join('. ')}</p>
    </section>
  );
}

function Row({ label, hint, cells, cols }: { label: string; hint?: string; cells: string[]; cols: Forecast['scenarios'] }) {
  return (
    <tr>
      <th scope="row" style={{ fontWeight: 400 }}>{label}{hint && <span className="cap" style={{ fontSize: 'var(--fs-label)', marginLeft: 6 }}>{hint}</span>}</th>
      {cells.map((c, i) => <td key={cols[i]!.key} className={`mono ${cols[i]!.key === 'month' ? s.mid : ''}`}>{c}</td>)}
    </tr>
  );
}

function Categories({ rows, month }: { rows: CategoryRow[]; month: string }) {
  return (
    <section className={s.section} aria-label="Which category breaks first">
      <div className={s.head}>
        <h2 className="h2">Which category breaks first</h2>
        <TextLink mono href="/budget/limits">set or change limits →</TextLink>
      </div>
      <div className={s.legend}>
        <span><i data-k="spent" />spent</span>
        <span><i data-k="proj" className="hatch" />added by month end at this pace</span>
        <span><i data-k="tick" />limit or plan</span>
      </div>
      <div className={s.cats}>
        <div className={`${s.cat} ${s.catHead} lbl`}><span>Category</span><span>Spent against the line</span><span style={{ textAlign: 'right' }}>Spent of line</span><span>Reaches the line</span></div>
        {rows.map((r) => {
          const v = verdictText(r, month);
          const ratio = r.lineMinor > 0 ? r.spentMinor / r.lineMinor : 1;
          const colour = r.verdict === 'over' ? 'danger' : ratio >= 0.8 ? 'warn' : 'ink';
          const projWidth = Math.max(0, r.projectedPct - r.spentPct);
          return (
            <div key={r.id} className={s.cat}>
              <span className="row-title">{r.name}</span>
              <div className={s.track} role="img" aria-label={`${r.name}: ${plain(r.spentMinor)} of ${plain(r.lineMinor)}, heading for ${plain(r.projectedMinor)}`}>
                <div className={s.fill} data-c={colour} style={{ width: `${r.spentPct.toFixed(1)}%` }} />
                {projWidth > 0 && <div className={`${s.proj} hatch`} style={{ left: `${r.spentPct.toFixed(1)}%`, width: `${projWidth.toFixed(1)}%` }} />}
                <div className={s.tick} style={{ left: '70%' }} />
              </div>
              <span className={`mono ${s.catSpent}`}>{plain(r.spentMinor)} of {plain(r.lineMinor)}</span>
              <span>
                <span className={r.verdict === 'inside' ? s.good : r.verdict === 'plan' ? undefined : s.bad} style={r.verdict === 'plan' ? { fontWeight: 500 } : undefined}>{v.text}</span>
                {v.when && <span className={`mono ${s.when}`}>{v.when}</span>}
                {r.verdict === 'plan' && <span className={`mono ${s.when}`}>no limit set</span>}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** The last six months and "against a usual month": what the Trends page showed. */
function History() {
  const months = useApi<ReportMonthsRes>(`/reports/months?range=${RANGE}`);
  const matrix = useApi<ReportMatrixRes>(`/reports/category-matrix?range=${RANGE}`);
  const m = months.data;
  const sentence = m ? headline(m) : null;
  const month = m ? monthName(m.end) : null;
  return (
    <>
      <section className={s.section} aria-label={`The last ${RANGE} months`}>
        <div className={s.head}>
          <h2 className="h2">The last {RANGE} months</h2>
          {m && m.averages.fullMonths > 0 && (
            <div className={s.legend} style={{ margin: 0 }}>
              <span><i data-k="in" />money in</span>
              <span><i data-k="out" />money out</span>
              <span><i data-k="proj" className="hatch" />where {month} ends at this pace</span>
            </div>
          )}
        </div>
        {sentence && <p className={`lead ${s.headline}`}>{sentence}</p>}
        {m ? (
          m.averages.fullMonths === 0
            ? <Empty>The last six months appear after your first full month.</Empty>
            : <div className={s.cols}><MonthChart chart={trendsChart(m)} /></div>
        ) : months.error ? (
          <div style={{ padding: '12px 0' }}>
            <ErrorLine>{errorText(months.error, 'Could not load the last months.')}</ErrorLine>
            <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void months.mutate()}>Try again</TextLink></div>
          </div>
        ) : <Loading />}
      </section>

      {m && m.averages.fullMonths > 0 && (
        <section className={`${s.section} ${s.list}`} aria-label={`${month} against a usual month`}>
          <div className={`lbl ${s.listHead}`}>{month} against a usual month</div>
          {matrix.data ? (
            usualRows(matrix.data).map((r) => (
              <div key={r.id} className={s.urow}>
                <span className={`row-title ${s.nm}`}>{r.name}</span>
                <span className={`mono ${s.usually}`}>{r.usually}</span>
                <span className={`mono ${s.heading}`}>{r.heading}</span>
                <span className={`mono ${s.change}`}>{r.change}</span>
              </div>
            ))
          ) : matrix.error ? (
            <div style={{ padding: '12px 0' }}>
              <ErrorLine>{errorText(matrix.error, 'Could not load the comparison.')}</ErrorLine>
              <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void matrix.mutate()}>Try again</TextLink></div>
            </div>
          ) : <Loading />}
        </section>
      )}
    </>
  );
}
