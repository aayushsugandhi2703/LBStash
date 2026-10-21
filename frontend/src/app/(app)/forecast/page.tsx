'use client';
import { inr, inrSigned, monthName, shortMonth } from '@/common';
import { CHART, type Forecast, type ForecastChart, type PaceKey, type RepeatLeft } from '@/features/forecast';
import { ForecastFrame, Lead, Pager, Pending } from './parts';
import { useForecast } from './use-forecast';
import s from './page.module.css';

export default function ForecastPage() {
  const { month, model, errorMessage, retry } = useForecast();
  const left = model?.f.daysLeft ?? 0;
  const hint = !model ? ' ' : left === 0 ? `Last day of ${monthName(model.input.month)}` : `${left} ${left === 1 ? 'day' : 'days'} left in ${monthName(model.input.month)}`;

  return (
    <ForecastFrame active="month" model={model} month={month} hint={hint}>
      {model ? (
        <>
          <Lead parts={model.f.lead} />
          {!model.f.empty && (
            <>
              <ChartSection f={model.f} chart={model.chart} hasPlan={model.input.planFlexMinor > 0} />
              {model.f.daysLeft > 0 && <LeftOn f={model.f} month={model.input.month} days={model.input.daysInMonth} repeats={model.left.items} />}
            </>
          )}
          <Pager left={{ text: 'Next: what runs out first' }} right={{ href: '/forecast/categories', label: 'Categories →' }} />
        </>
      ) : <Pending error={errorMessage} retry={retry} />}
    </ForecastFrame>
  );
}

function ChartSection({ f, chart, hasPlan }: { f: Forecast; chart: ForecastChart; hasPlan: boolean }) {
  return (
    <section className={s.section} aria-label="Spending this month">
      <div className="sechead ruled">
        <h2 className="h2">Spending this month</h2>
        <span className="lbl" style={{ textTransform: 'none' }}>repeats not included</span>
      </div>
      <div className={s.legend}>
        <span><i />so far</span>
        {f.daysLeft > 0 && <span><i data-k="dash" />at this pace</span>}
        {f.hasRange && <span><i data-k="range" />possible range</span>}
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
      {c.runOut && (
        <>
          <path className={s.leader} d={`M${c.runOut.x.toFixed(1)} ${(c.runOut.y + 6).toFixed(1)} V${(c.runOut.y + 33).toFixed(1)}`} />
          <circle className={s.dotRun} cx={c.runOut.x} cy={c.runOut.y} r="5" />
        </>
      )}
      <text className={`${s.t} ${s.tText} ${s.tEnd}`} x={c.todayX - 6} y={top + 14}>{c.todayLabel}</text>
      {c.planY !== null && <text className={`${s.t} ${s.tPlan}`} x={left + 4} y={c.planY - 7}>plan</text>}
      {c.runOut && <text className={`${s.t} ${s.tBad} ${s.tEnd}`} x={c.runOut.x + 5} y={c.runOut.y + 47}>{c.runOut.label}</text>}
      {c.ends.map((e) => <text key={e.label} className={`${s.t} ${e.strong ? `${s.tInk} ${s.tStrong}` : ''}`} x={right + 8} y={e.y + 4}>{e.label}</text>)}
      {c.xTicks.map((t) => <text key={t.x} className={`${s.t} ${s.tMid} ${t.today ? `${s.tPlan} ${s.tStrong}` : ''}`} x={t.x} y={bottom + 20}>{t.label}</text>)}
    </svg>
  );
}

const LIKE: Record<PaceKey, string> = { best: 'Like your best week', month: 'Like this month', recent: 'Like the last 7 days' };
const ORDER: PaceKey[] = ['best', 'month', 'recent'];

function LeftOn({ f, month, days, repeats }: { f: Forecast; month: string; days: number; repeats: RepeatLeft[] }) {
  const repeatsTotal = repeats.reduce((t, i) => t + i.amountMinor, 0);
  return (
    <section className={s.section} aria-label={`What you will have left on ${shortMonth(month)} ${days}`}>
      <div className="sechead ruled">
        <h2 className="h2">What you will have left on {shortMonth(month)} {days}</h2>
      </div>
      <div className={s.outs}>
        {ORDER.map((k) => f.scenarios.find((c) => c.key === k)!).map((c) => (
          <div key={c.key} className={s.out} data-on={c.key === 'month'}>
            <div className="lbl">{LIKE[c.key]}</div>
            <div className={`mono ${s.outFig}`}>{inrSigned(c.balanceEndMinor)}</div>
            <div className="cap">spending {inr(Math.round(c.ratePerDay / 100) * 100)} a day</div>
          </div>
        ))}
      </div>
      {repeatsTotal > 0 && <p className={`cap ${s.outNote}`}>Includes {inr(repeatsTotal)} of repeats still to come.</p>}
    </section>
  );
}
