import Link from 'next/link';
import type { SummaryRow } from '@/features/setup';
import s from './page.module.css';

/** The all-done view: what is connected, one sentence about what happens next, and where to go. */
export function StepDone({ rows }: { rows: SummaryRow[] }) {
  return (
    <div className={`rise ${s.done}`}>
      <div className={s.summary}>
        {rows.map((r) => (
          <div key={r.label} className={s.sumRow}>
            <span aria-hidden="true" className={s.dot} data-ok={r.ok} />
            <span className={s.sumLabel}>{r.label}</span>
            <span className={`mono ${s.sumValue}`} data-ok={r.ok}>{r.value}</span>
          </div>
        ))}
      </div>
      <div className={`lead ${s.next}`}>Next time your bank messages you, it shows up here and in Telegram within seconds. Tag it once per new payee.</div>
      <div className={s.actions}>
        <Link href="/" className="btn lg">Open Now</Link>
        <Link href="/ledger" className={s.quiet}>See the Ledger</Link>
      </div>
    </div>
  );
}
