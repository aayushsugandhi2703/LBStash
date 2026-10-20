import { formatInr, type Paise } from './money';

/** Every UI figure is paise from the API; these turn them into text (design system §11). */
export const TZ = 'Asia/Kolkata';

/** ₹37,591 (no sign). */
export const inr = (p: Paise): string => `₹${formatInr(Math.abs(p))}`;
/** Balance that may be negative: −₹1,200. */
export const inrSigned = (p: Paise): string => (p < 0 ? '−' : '') + inr(p);
/** Grouped number without the rupee sign: 45,500. */
export const plain = (p: Paise): string => formatInr(Math.abs(p));
/** Same with a true minus for negatives: −1,200. */
export const figure = (p: Paise): string => (p < 0 ? '−' : '') + plain(p);
/** List amount: +50,000 for money in, −386 for money out. */
export const listAmount = (p: Paise, type: 'debit' | 'credit'): string => `${type === 'credit' ? '+' : '−'}${plain(p)}`;
/** Axis label: 41.2K, 60K. */
export const compactK = (p: Paise): string => {
  const k = p / 100000;
  return `${Number.isInteger(k) ? k : k.toFixed(1)}K`;
};
/** 11.8% in stats; verdicts use whole numbers. */
export const pct1 = (ratio: number): string => `${(ratio * 100).toFixed(1)}%`;
/** Whole rupees: averages and per-day figures show ₹539, never ₹539.43. */
export const wholeRupees = (p: Paise): Paise => Math.round(p / 100) * 100;

const parts = (iso: string | Date, tz: string, opts: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: tz, ...opts }).formatToParts(new Date(iso));
const part = (p: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes) => p.find((x) => x.type === type)?.value ?? '';

/** OCT 18 (mono caps in lists). */
export function monthDay(iso: string | Date, tz = TZ): string {
  const p = parts(iso, tz, { month: 'short', day: 'numeric' });
  return `${part(p, 'month').toUpperCase()} ${part(p, 'day')}`;
}
/** 6:42 pm */
export function timeOfDay(iso: string | Date, tz = TZ): string {
  const p = parts(iso, tz, { hour: 'numeric', minute: '2-digit', hour12: true });
  return `${part(p, 'hour')}:${part(p, 'minute')} ${part(p, 'dayPeriod').toLowerCase()}`;
}

const monthIn = (key: string, month: 'long' | 'short', locale: string) =>
  new Intl.DateTimeFormat(locale, { month, timeZone: 'UTC' }).format(new Date(`${key}-01T00:00:00Z`));
/** "October" for 2026-10. */
export const monthName = (key: string): string => monthIn(key, 'long', 'en-GB');
/** "Sep" for 2026-09 (en-GB would spell it "Sept"; the design says Sep). */
export const shortMonth = (key: string): string => monthIn(key, 'short', 'en-US');
/** "November" for the month after `key` (December rolls into January). */
export const nextMonthName = (key: string): string => {
  const [y, m] = key.split('-').map(Number) as [number, number];
  return monthName(m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`);
};

/** "Rent" → "rent", "SIP" stays: lets "rent and SIP left out" read as a sentence. */
export const inSentence = (name: string): string => (name === name.toUpperCase() ? name : name.charAt(0).toLowerCase() + name.slice(1));
/** a, b and c */
export function joinPlain(items: string[]): string {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}
