'use client';
import type { ReportMatrixRes, ReportMonthsRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { Empty, ErrorLine, Loading, TextLink } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { monthName } from '@/common';
import { headline, trendsChart, type TrendStat, trendStats, usualRows } from '@/features/trends';
import { MonthChart } from './month-chart';
import s from './page.module.css';

const RANGE = 6;
const WAITING: TrendStat[] = ['Avg monthly spend', 'Avg kept', 'Balance since start'].map((label) => ({ label, value: '—', note: '', tone: 'plain' }));

export default function TrendsPage() {
  const months = useApi<ReportMonthsRes>(`/reports/months?range=${RANGE}`);
  const matrix = useApi<ReportMatrixRes>(`/reports/category-matrix?range=${RANGE}`);
  const m = months.data;
  const stats = m ? trendStats(m) : null;
  const sentence = m ? headline(m) : null;
  const month = m ? monthName(m.end) : null;

  return (
    <AppShell
      home="trends" glyph="trends" title="Trends"
      description={`How your money has moved over the last ${RANGE} months.`}
      aside={
        <div className={s.stats}>
          {(stats ?? WAITING).map((st) => (
            <div key={st.label} className={s.stat}>
              <div className="lbl">{st.label}</div>
              <div className={`${s.statFig} ${st.tone === 'credit' ? 'credit' : ''}`}>{st.value}</div>
              <div className={`mono ${s.statNote}`}>{st.note || ' '}</div>
            </div>
          ))}
        </div>
      }
    >
      {sentence && <p className={`lead opt ${s.headline}`}>{sentence}</p>}

      <section className={s.panel} aria-label="Money in and out">
        <div className={s.panelHead}>
          <h2 className="h2">Money in and out</h2>
          {m && m.averages.fullMonths > 0 && (
            <div className={`mono ${s.legend}`}>
              <span><i style={{ background: 'var(--g-accent-v)' }} aria-hidden="true" />money in</span>
              <span><i style={{ background: 'var(--g-ink-v)' }} aria-hidden="true" />money out</span>
              <span><i className="hatch" aria-hidden="true" />where {month} ends at this pace</span>
            </div>
          )}
        </div>
        {m ? (
          m.averages.fullMonths === 0
            ? <Empty>Trends appear after your first full month.</Empty>
            : <MonthChart chart={trendsChart(m)} />
        ) : months.error ? (
          <div style={{ padding: '12px 0' }}>
            <ErrorLine>{errorText(months.error, 'Could not load your trends.')}</ErrorLine>
            <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void months.mutate()}>Try again</TextLink></div>
          </div>
        ) : <Loading />}
      </section>

      {m && m.averages.fullMonths > 0 && (
        <section className={`opt2 ${s.list}`} aria-label={`${month} against a usual month`}>
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
    </AppShell>
  );
}
