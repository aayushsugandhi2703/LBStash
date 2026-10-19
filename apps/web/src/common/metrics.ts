import type { Paise } from './money';

export type LimitStatus = 'over' | 'close' | 'fast' | 'ok';

/** True when spent has reached `pct` percent of the limit (integer maths, no float drift). */
const reaches = (spent: Paise, limit: Paise, pct: number): boolean => limit > 0 && spent * 100 >= pct * limit;

/** over ≥ 100% · close ≥ alert level · fast = pace passes the limit while still under the alert level · else ok. */
export function limitStatus(p: { spent: Paise; limit: Paise; alertPct: number; projected: Paise }): LimitStatus {
  if (reaches(p.spent, p.limit, 100)) return 'over';
  if (reaches(p.spent, p.limit, p.alertPct)) return 'close';
  return p.projected > p.limit ? 'fast' : 'ok';
}
