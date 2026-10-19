import type { Paise } from './money';

/** Share of `max` as a percentage clamped to 0..100 (chart geometry is always % of the plot). */
export const pct = (v: number, max: number): number => (max > 0 ? Math.min(100, Math.max(0, (v / max) * 100)) : 0);
/** Percentage rounded for CSS: 46.123456 → 46.123. */
export const css3 = (n: number): number => Number(n.toFixed(3));

/** First 1-2-5 style rung (in paise, starting at `minRupees`) that holds `max`. */
function ladder(max: Paise, minRupees: number, mantissas: number[], mult: number): Paise {
  for (let rupees = minRupees; ; rupees *= 10) {
    for (const m of mantissas) {
      const v = m * rupees * mult * 100;
      if (v >= max) return v;
    }
  }
}

/** Day plot scale: ₹100, 200, 500, 1,000 …, with gridlines at the top and half way. */
export function dayScale(maxPaise: Paise): { max: Paise; mid: Paise } {
  const max = ladder(maxPaise, 100, [1, 2, 5], 1);
  return { max, mid: max / 2 };
}

/** Month plot scale: three equal parts of a 1-2-2.5-5 step (60K with 40K and 20K), never below ₹3,000. */
export function monthScale(maxPaise: Paise): { max: Paise; ticks: Paise[] } {
  const max = ladder(maxPaise, 1000, [1, 2, 2.5, 5], 3);
  return { max, ticks: [max, (max / 3) * 2, max / 3] };
}
