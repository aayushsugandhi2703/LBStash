/** Money is integer paise (1 rupee = 100 paise), never a float. */
export type Paise = number;

const PAISE_PER_RUPEE = 100;

/** "450", "450.5", "1,234.50", "₹ 450.00" → paise. Throws on junk or more than 2 decimals. */
export function parseRupees(input: string): Paise {
  const cleaned = input.replace(/[₹\s,]/g, '').replace(/^rs\.?/i, '').replace(/^inr/i, '');
  const m = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!m) throw new TypeError(`not an amount: ${input}`);
  const paise = Number(m[2]) * PAISE_PER_RUPEE + Number((m[3] ?? '').padEnd(2, '0') || '0');
  return m[1] ? -paise : paise;
}

/** Indian grouping: 3759100 → "37,591"; 123456789 → "12,34,567.89". Decimals only when non-zero. */
export function formatInr(paise: Paise, opts: { symbol?: boolean; forceDecimals?: boolean } = {}): string {
  if (!Number.isSafeInteger(paise)) throw new TypeError('amount must be an integer number of paise');
  const abs = Math.abs(paise);
  const rem = abs % PAISE_PER_RUPEE;
  const s = String(Math.trunc(abs / PAISE_PER_RUPEE));
  const rest = s.slice(0, -3);
  const grouped = rest ? `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${s.slice(-3)}` : s;
  const decimals = rem || opts.forceDecimals ? `.${String(rem).padStart(2, '0')}` : '';
  return `${paise < 0 ? '-' : ''}${opts.symbol ? '₹' : ''}${grouped}${decimals}`;
}
