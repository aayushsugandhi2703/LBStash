import { parseTag } from '@/common';
import type { PlanPutReq } from '@/contracts';

/** Plan page logic (docs/ui-spec/03-plan). Pure: the page keeps a draft and calls these. All money is paise. */

/** Neutral ramp for the split bar and row swatches, in order (design system §1). */
export const RAMP = ['#0E0E10', '#2C2C33', '#4A4A53', '#6B6B73', '#8E8E98', '#B1B1BA', '#CFCFD6', '#E3E3E8', '#EDEDF1'] as const;
export const MAX_LINES = RAMP.length;
const TOTAL_STEP = 500_000; // ₹5,000
const LINE_STEP = 50_000; // ₹500

interface DraftLine {
  /** Present for a category that exists; a line typed as a new tag has only `tag` until the server resolves it. */
  categoryId?: string;
  tag?: string;
  /** Stored (lowercase) category name. */
  name: string;
  allocatedMinor: number;
  spentMinor: number;
}
export interface Draft { totalMinor: number; lines: DraftLine[] }

export const monthName = (key: string): string =>
  new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(new Date(`${key}-01T00:00:00Z`));
export const nextMonthName = (key: string): string => {
  const [y, m] = key.split('-').map(Number) as [number, number];
  return monthName(`${m === 12 ? y + 1 : y}-${String(m === 12 ? 1 : m + 1).padStart(2, '0')}`);
};

export function planMath(d: Draft) {
  const assigned = d.lines.reduce((s, l) => s + l.allocatedMinor, 0);
  const unassigned = d.totalMinor - assigned;
  return { assigned, unassigned, over: unassigned < 0, base: Math.max(d.totalMinor, assigned, 1) };
}

export const stepTotal = (d: Draft, dir: 1 | -1): Draft => ({ ...d, totalMinor: Math.max(0, d.totalMinor + dir * TOTAL_STEP) });
export const stepLine = (d: Draft, index: number, dir: 1 | -1): Draft => ({
  ...d, lines: d.lines.map((l, i) => (i === index ? { ...l, allocatedMinor: Math.max(0, l.allocatedMinor + dir * LINE_STEP) } : l)),
});

interface LineView { remainMinor: number; over: boolean; pct: number; colour: 'accent' | 'warn' | 'danger' }
/** Used bar: green under 80%, yellow from 80%, red once spent passes the plan. Width is capped at 100. */
export function lineView(l: DraftLine): LineView {
  const remainMinor = l.allocatedMinor - l.spentMinor;
  const over = remainMinor < 0;
  const pct = l.allocatedMinor > 0 ? Math.min(100, (l.spentMinor / l.allocatedMinor) * 100) : 0;
  return { remainMinor, over, pct, colour: over ? 'danger' : pct >= 80 ? 'warn' : 'accent' };
}

/** Width in % of each split-bar segment and of the free (unassigned) tail. */
export function segments(d: Draft): { widths: number[]; free: number } {
  const { base, unassigned } = planMath(d);
  return { widths: d.lines.map((l) => (l.allocatedMinor / base) * 100), free: unassigned > 0 ? (unassigned / base) * 100 : 0 };
}

type AddResult = { ok: true; draft: Draft; added: boolean } | { ok: false; message: string };
/** Typing a tag adds a line with 0 planned (the server creates the category on save). An existing name does nothing. */
export function addTag(d: Draft, raw: string): AddResult {
  if (!raw.replace(/#/g, '').trim()) return { ok: true, draft: d, added: false };
  const parsed = parseTag(raw);
  if (!parsed.ok) return { ok: false, message: parsed.error };
  const name = parsed.tag;
  if (d.lines.some((l) => l.name === name)) return { ok: true, draft: d, added: false };
  if (d.lines.length >= MAX_LINES) return { ok: false, message: `A plan shows up to ${MAX_LINES} categories.` };
  return { ok: true, added: true, draft: { ...d, lines: [...d.lines, { tag: name, name, allocatedMinor: 0, spentMinor: 0 }] } };
}

/** Up to three one-tap tags: the user's own categories not on the plan yet. */
export function suggestions(d: Draft, known: string[]): string[] {
  const taken = new Set(d.lines.map((l) => l.name));
  const out: string[] = [];
  for (const n of known) if (!taken.has(n) && !out.includes(n)) out.push(n);
  return out.slice(0, 3);
}

export const toPutBody = (d: Draft): PlanPutReq => ({
  totalMinor: d.totalMinor,
  lines: d.lines.map((l) => (l.categoryId ? { categoryId: l.categoryId, allocatedMinor: l.allocatedMinor } : { tag: l.tag ?? l.name, allocatedMinor: l.allocatedMinor })),
});

export interface PlanResponse {
  totalMinor: number;
  lines: { categoryId: string; categoryName: string; allocatedMinor: number; spentMinor: number }[];
}
export const draftFrom = (p: PlanResponse): Draft => ({
  totalMinor: p.totalMinor,
  lines: p.lines.map((l) => ({ categoryId: l.categoryId, name: l.categoryName, allocatedMinor: l.allocatedMinor, spentMinor: l.spentMinor })),
});
