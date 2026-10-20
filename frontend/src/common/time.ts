/** Time-zone aware month and day helpers. Month boundaries and "today" always use the user's zone. */
type MonthKey = string; // 'YYYY-MM'
type DateKey = string; // 'YYYY-MM-DD'

const pad = (n: number, w = 2) => String(n).padStart(w, '0');

const fmtCache = new Map<string, Intl.DateTimeFormat>();
function fmt(tz: string): Intl.DateTimeFormat {
  let f = fmtCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' });
    fmtCache.set(tz, f);
  }
  return f;
}

function tzParts(date: Date, tz: string): { y: number; m: number; d: number } {
  const o: Record<string, number> = {};
  for (const p of fmt(tz).formatToParts(date)) if (p.type !== 'literal') o[p.type] = Number(p.value);
  return { y: o.year!, m: o.month!, d: o.day! };
}

export function dateKey(date: Date, tz: string): DateKey {
  const p = tzParts(date, tz);
  return `${p.y}-${pad(p.m)}-${pad(p.d)}`;
}

function parseMonth(key: MonthKey): { y: number; m: number } {
  const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(key);
  if (!m) throw new TypeError(`not a month: ${key}`);
  return { y: Number(m[1]), m: Number(m[2]) };
}

export function daysInMonth(key: MonthKey): number {
  const { y, m } = parseMonth(key);
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

export function addMonths(key: MonthKey, n: number): MonthKey {
  const { y, m } = parseMonth(key);
  const idx = y * 12 + (m - 1) + n;
  const yy = Math.floor(idx / 12);
  return `${pad(yy, 4)}-${pad(idx - yy * 12 + 1)}`;
}

/** Day 18 of 31 and so on, for "today" in `tz`. */
export function monthProgress(now: Date, tz: string): { month: MonthKey; day: number; days: number; daysLeft: number } {
  const p = tzParts(now, tz);
  const month = `${p.y}-${pad(p.m)}`;
  const days = daysInMonth(month);
  return { month, day: p.d, days, daysLeft: days - p.d + 1 };
}

/** Add whole months, keeping the wanted day but clamping short months (31st → 30th/28th). */
export function addMonthsClamped(date: DateKey, n: number, wantedDay?: number): DateKey {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  const target = addMonths(`${pad(y, 4)}-${pad(m)}`, n);
  return `${target}-${pad(Math.min(wantedDay ?? d, daysInMonth(target)))}`;
}

export function addDays(date: DateKey, n: number): DateKey {
  const [y, m, d] = date.split('-').map(Number) as [number, number, number];
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}
