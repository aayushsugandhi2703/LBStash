import { Tip } from '@/components/ui';
import type { TrendsChart } from '@/features/trends';
import s from './month-chart.module.css';

/** Money in and out per month, with the month in progress carrying a hatched block up to where it ends at this pace. */
export function MonthChart({ chart }: { chart: TrendsChart }) {
  return (
    <div className={s.plot} role="group" aria-label={chart.summary}>
      {chart.grid.map((g) => (
        <div key={g.label} className={s.grid} style={{ top: `${g.topPct}%` }}><span className="mono">{g.label}</span></div>
      ))}
      <div className={s.grid} data-base="true" style={{ top: '100%' }}><span className="mono">0</span></div>
      <span className={`mono ${s.keptLbl}`}>kept</span>
      <div className={s.cols}>
        {chart.columns.map((m, i) => (
          <button
            key={m.month} type="button" className={`${s.grp} has-tip`}
            aria-label={[m.tip.title, ...m.tip.lines, m.tip.kept].filter(Boolean).join(', ')}
          >
            <span className="vbar" data-c="accent" style={{ ...bar(m.inPct), animationDelay: `${(i * 0.06).toFixed(2)}s` }} />
            <span className={s.outWrap}>
              {m.pacePct > 0 && <span className="vbar hatch" style={{ ...fill(m.pacePct), marginBottom: 2, animationDelay: `${(i * 0.06 + 0.1).toFixed(2)}s` }} />}
              <span className="vbar" data-c="ink" style={{ ...fill(m.outPct), animationDelay: `${(i * 0.06 + 0.03).toFixed(2)}s` }} />
            </span>
            <span className={`mono ${s.label}`}>
              {m.label}
              <span className={s.kept} data-none={!m.active}>{m.keptText}</span>
            </span>
            <Tip
              title={m.tip.title}
              lines={[...m.tip.lines, ...(m.tip.kept ? [<span key="kept" className={s.tipKept}>{m.tip.kept}</span>] : [])]}
              style={m.tipSide === 'right' ? { left: '100%', marginLeft: 4, top: 8 } : { right: '100%', marginRight: 4, top: 8 }}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

const bar = (pct: number) => ({ display: 'block', width: '30%', maxWidth: 30, height: `${pct}%` });
const fill = (pct: number) => ({ display: 'block', width: '100%', height: `${pct}%` });
