'use client';
import type { CSSProperties, ReactNode } from 'react';
import { inr } from '@/common';
import { type Stem, stems, ticks, timelineLabel } from '@/features/repeats';
import type { RecurringRuleDto } from '@/contracts';
import s from './page.module.css';

/** Lollipop timeline of the next 30 days: one ink stem per upcoming payment, tallest = biggest amount. */
export function Timeline({ rules, today, status }: { rules: RecurringRuleDto[]; today: string | null; status?: ReactNode }) {
  const list: Stem[] = today ? stems(rules, today) : [];
  return (
    <div className={s.timeline}>
      <div className={s.timelineInner}>
        <div className={s.plot} role={status ? 'group' : 'img'} aria-label={status ? undefined : timelineLabel(list)}>
          {status ? <div className={s.plotEmpty}>{status}</div> : list.length === 0 && <div className={`${s.plotEmpty} cap`}>Nothing leaves in the next 30 days.</div>}
          {list.map((st, i) => (
            <div key={st.key} className={s.stemWrap} style={{ left: `${st.leftPct.toFixed(3)}%`, '--h': `${st.heightPct.toFixed(2)}%` } as CSSProperties}>
              <div className={s.label} data-a={st.align}>
                <div className={s.n}>{st.name}</div>
                <div className={`mono ${s.a}`}>{inr(st.amountMinor)}</div>
              </div>
              <div className={`vbar ${s.stem}`} data-c="ink" style={{ animationDelay: `${i * 0.1}s` }} />
              <div className={s.cap} />
            </div>
          ))}
        </div>
        <div className={s.axis} aria-hidden="true">
          {today && ticks(today).map((t) => (
            <span key={t.day}>
              <span className={s.tick} data-l={t.label !== null} style={{ left: `${t.leftPct.toFixed(3)}%` }} />
              {t.label && <span className={`mono ${s.tickLbl}`} data-p={t.day === 0 ? 'first' : t.day === 30 ? 'last' : undefined} style={{ left: `${t.leftPct.toFixed(3)}%` }}>{t.label}</span>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
