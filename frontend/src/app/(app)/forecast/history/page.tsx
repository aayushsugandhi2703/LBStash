'use client';
import type { ReportMonthsRes } from '@/contracts';
import { monthName } from '@/common';
import { Empty, ErrorLine, Loading, TextLink } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { headlineParts, trendsChart } from '@/features/trends';
import { ForecastFrame, Lead, Pager } from '../parts';
import { useForecast } from '../use-forecast';
import { MonthChart } from '../month-chart';
import s from '../page.module.css';

const RANGE = 6;

export default function ForecastHistoryPage() {
  const { month, model } = useForecast();
  const months = useApi<ReportMonthsRes>(`/reports/months?range=${RANGE}`);
  const m = months.data;
  const lead = m ? headlineParts(m) : null;
  const current = m ? monthName(m.end) : null;
  return (
    <ForecastFrame active="history" model={model} month={month} hint="Compared with before">
      {lead && <Lead parts={lead} />}
      <section className={s.section} aria-label="Last six months">
        <div className="sechead ruled">
          <h2 className="h2">Last six months</h2>
        </div>
        {m && m.averages.fullMonths > 0 && (
          <div className={s.legend}>
            <span><i data-k="in" />money in</span>
            <span><i data-k="out" />money out</span>
            <span><i data-k="proj" className="hatch" />still to come in {current}</span>
          </div>
        )}
        {m ? (
          m.averages.fullMonths === 0
            ? <Empty>Shows after your first full month.</Empty>
            : <div className={s.cols}><MonthChart chart={trendsChart(m)} /></div>
        ) : months.error ? (
          <div style={{ padding: '12px 0' }}>
            <ErrorLine>{errorText(months.error, 'Could not load the last months.')}</ErrorLine>
            <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void months.mutate()}>Try again</TextLink></div>
          </div>
        ) : <Loading />}
      </section>
      <Pager left={{ href: '/forecast/categories', label: '← Categories' }} right={{ href: '/budget', label: 'Your plan →' }} />
    </ForecastFrame>
  );
}
