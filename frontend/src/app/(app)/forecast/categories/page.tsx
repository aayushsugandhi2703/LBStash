'use client';
import type { ReportMatrixRes, ReportMonthsRes } from '@/contracts';
import { plain } from '@/common';
import { ErrorLine, Loading, TextLink } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { categoriesLead, type CategoryRow, verdictText } from '@/features/forecast';
import { usualRows } from '@/features/trends';
import { ForecastFrame, Lead, Pager, Pending } from '../parts';
import { useForecast } from '../use-forecast';
import s from '../page.module.css';

const RANGE = 6;

export default function ForecastCategoriesPage() {
  const { month, model, errorMessage, retry } = useForecast();
  return (
    <ForecastFrame active="categories" model={model} month={month} hint="What runs out first">
      {model ? (
        <>
          <Lead parts={categoriesLead(model.rows, model.input.month)} />
          {model.rows.length > 0 && <Categories rows={model.rows} month={model.input.month} />}
          <Usual />
          <Pager left={{ href: '/forecast', label: '← This month' }} right={{ href: '/forecast/history', label: 'Six months →' }} />
        </>
      ) : <Pending error={errorMessage} retry={retry} />}
    </ForecastFrame>
  );
}

function Categories({ rows, month }: { rows: CategoryRow[]; month: string }) {
  return (
    <section className={s.section} aria-label="Spending by category">
      <div className="sechead ruled">
        <h2 className="h2">Spending by category</h2>
        <TextLink mono href="/budget/limits">Set limits →</TextLink>
      </div>
      <div className={s.legend}>
        <span><i data-k="spent" />spent</span>
        <span><i data-k="proj" className="hatch" />still to come</span>
        <span><i data-k="tick" />plan</span>
      </div>
      <div className={s.cats}>
        {rows.map((r) => {
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
              <span className={r.verdict === 'inside' ? s.good : s.bad}>{verdictText(r, month)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** October at this pace against a usual month; shown once there is a full month to compare with. */
function Usual() {
  const months = useApi<ReportMonthsRes>(`/reports/months?range=${RANGE}`);
  const matrix = useApi<ReportMatrixRes>(`/reports/category-matrix?range=${RANGE}`);
  if (!months.data || months.data.averages.fullMonths === 0) return null;
  const rows = matrix.data ? usualRows(matrix.data) : null;
  if (rows && rows.length === 0) return null;
  return (
    <section className={s.section} aria-label="Compared with a usual month">
      <div className="sechead ruled">
        <h2 className="h2">Compared with a usual month</h2>
      </div>
      {rows ? (
        <>
          <div className={s.usualWrap}>
            {rows.map((r) => (
              <div key={r.id} className={s.usual}>
                <span className="row-title">{r.name}</span>
                <span className="mono">{r.heading} <span className={s.vs}>vs {r.usually}</span></span>
                <span className={`mono ${r.dir === 'more' ? s.bad : r.dir === 'less' ? s.good : s.vs}`}>{r.change}</span>
              </div>
            ))}
          </div>
          <p className={`cap ${s.usualNote}`}>This month at your pace, against your usual month.</p>
        </>
      ) : matrix.error ? (
        <div style={{ padding: '12px 0' }}>
          <ErrorLine>{errorText(matrix.error, 'Could not load the comparison.')}</ErrorLine>
          <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void matrix.mutate()}>Try again</TextLink></div>
        </div>
      ) : <Loading />}
    </section>
  );
}
