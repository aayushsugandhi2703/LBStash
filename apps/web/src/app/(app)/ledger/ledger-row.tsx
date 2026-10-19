'use client';
import type { RowView } from '@/features/ledger';
import s from './page.module.css';

/** One line of the list (DATE, WHAT, TAG, SOURCE, AMOUNT). `tag it` and `split` open their wells under the row. */
export function LedgerRowItem({ v, tagging, onTag, onSplit }: {
  v: RowView; tagging: boolean; onTag: () => void; onSplit: () => void;
}) {
  return (
    <div className="row rise">
      <div className={`${s.cDate} ${s.date} mono`}>{v.date}</div>
      <div className={s.cWhat}>
        <div className={s.name} data-reversed={v.reversed}>
          {v.unaccounted && <span className={s.mark} aria-hidden="true" />}{v.name}
        </div>
        {v.note && <div className={`row-sub ${s.note}`}>{v.note}</div>}
      </div>
      <div className={`${s.cTag} ${s.tag}`}>
        {v.tag && <span className={`mono ${s.tagText}`}>{v.tag}</span>}
        {v.needsTag && (
          <button type="button" className={`link mono ${s.act} ${s.hot}`} aria-expanded={tagging} aria-label={`Tag ${v.name} ${v.amount}`} onClick={onTag}>tag it</button>
        )}
        {v.canSplit && <button type="button" className={`link mono ${s.act} ${s.quiet}`} aria-label={`Split ${v.name} ${v.amount}`} onClick={onSplit}>split</button>}
      </div>
      <div className={`${s.cSource} ${s.source} mono`}>{v.source}</div>
      <div className={`${s.cAmount} ${s.amount} mono ${v.credit ? 'credit' : 'debit'}`}>{v.amount}</div>
    </div>
  );
}
