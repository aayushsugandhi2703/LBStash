import { parseRupees } from './money';

/** Typing into a rupee box. The value is canonical ("1250", "1250.5"); the display is grouped the Indian way. */
export interface AmountOpts {
  /** Allow up to two decimals (bank balance, split parts). Credit and Needs a look amounts are whole rupees. */
  decimals?: boolean;
  /** Digits before the decimal point. */
  maxDigits?: number;
}

const DEFAULT_MAX = 9;

/** "5x0,000" → "50000"; "007" → "7"; with decimals "0.5" and "12." survive so the next key can land. */
export function cleanAmount(raw: string, o: AmountOpts = {}): string {
  let int = '';
  let frac: string | null = null;
  for (const ch of raw) {
    if (ch >= '0' && ch <= '9') {
      if (frac === null) int += ch;
      else if (frac.length < 2) frac += ch;
    } else if (ch === '.' && o.decimals && frac === null) frac = '';
  }
  int = int.replace(/^0+/, '').slice(0, o.maxDigits ?? DEFAULT_MAX);
  return frac !== null ? `${int || '0'}.${frac}` : int;
}

/** "1250000" → "12,50,000"; a typed decimal point is kept. */
export function groupIndian(canonical: string): string {
  const [int = '', frac] = canonical.split('.');
  const rest = int.slice(0, -3);
  const grouped = rest ? `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${int.slice(-3)}` : int;
  return frac === undefined ? grouped : `${grouped}.${frac}`;
}

/** What the box shows after the user typed `raw` with the caret at `caret`: value, text and new caret position. */
export function reformat(raw: string, caret: number, o: AmountOpts = {}): { value: string; display: string; caret: number } {
  const value = cleanAmount(raw, o);
  const display = groupIndian(value);
  // digits and the point before the caret stay before the caret
  let keep = 0;
  for (const ch of raw.slice(0, caret)) if ((ch >= '0' && ch <= '9') || ch === '.') keep++;
  keep = Math.min(keep, display.replace(/,/g, '').length);
  let pos = 0;
  for (let seen = 0; pos < display.length && seen < keep; pos++) if (display[pos] !== ',') seen++;
  return { value, display, caret: pos };
}

/** Canonical rupees → paise. "" and "0" are 0. */
export function toPaise(canonical: string): number {
  const [int = '', frac = ''] = canonical.split('.');
  return (Number(int) || 0) * 100 + Number(frac.padEnd(2, '0').slice(0, 2) || '0');
}

/** Paise → canonical rupees: 125000 → "1250", 125050 → "1250.5", 0 → "". */
export function fromPaise(paise: number): string {
  if (!Number.isFinite(paise) || paise <= 0) return '';
  const frac = String(paise % 100).padStart(2, '0').replace(/0+$/, '');
  const int = Math.trunc(paise / 100);
  return frac ? `${int}.${frac}` : String(int);
}

/** Quick-add links: add whole rupees to what is typed, never past the digit limit. */
export function addRupees(canonical: string, n: number, o: AmountOpts = {}): string {
  const cap = 10 ** (o.maxDigits ?? DEFAULT_MAX) - 1;
  const [int = '', frac] = canonical.split('.');
  const sum = Math.min(cap, (Number(int) || 0) + n);
  return frac ? `${sum}.${frac}` : String(sum);
}

/** What a person typed ("₹2,000", "2000.50") → paise, or null when it is not a positive amount. */
export function parseAmount(text: string): number | null {
  try {
    const p = parseRupees(text.trim());
    return p > 0 && Number.isSafeInteger(p) ? p : null;
  } catch { return null; }
}
