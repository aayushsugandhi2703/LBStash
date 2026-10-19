import { z } from 'zod';
import { dateKey, isoDateTime, monthKey, paise, uuid } from './common';


export const AttentionItem = z.discriminatedUnion('kind', [
  /** A limit at or above its alert level (WATCH). `category` is display-cased ("Fun"). */
  z.object({ kind: z.literal('limit'), category: z.string(), pct: z.number().int(), status: z.enum(['close', 'over']) }),
  /** Debits waiting for a tag (TAG). */
  z.object({ kind: z.literal('untagged'), count: z.number().int() }),
  /** Messages that could not be read (LOOK). */
  z.object({ kind: z.literal('needs_look'), count: z.number().int() }),
  /** Balance-check gaps booked as Unaccounted and not yet split or tagged. */
  z.object({ kind: z.literal('unaccounted'), count: z.number().int() }),
  /** The next recurring payment that will leave (NEXT). */
  z.object({ kind: z.literal('recurring'), name: z.string(), amount: paise, due: dateKey }),
]);
export type AttentionItem = z.infer<typeof AttentionItem>;

export const DashboardRes = z.object({
  month: monthKey,
  /** Day of the month "today" is on (the month's last day for past months, 0 for future months). */
  dayOfMonth: z.number().int(),
  daysInMonth: z.number().int(),
  balance: z.object({ carriedOver: paise, income: paise, spent: paise, available: paise }),
  /** `perDay` is plan left ÷ days left (today included), rounded down to whole rupees. */
  safeToSpend: z.object({ planLeft: paise, daysLeft: z.number().int(), perDay: paise }),
  /** Spent per category, biggest first, then "Still available" last. Sums to carried over + income. */
  flow: z.array(z.object({ name: z.string(), amount: paise })),
  attention: z.array(AttentionItem),
  lastCapturedAt: isoDateTime.nullable(),
  untaggedCount: z.number().int(),
  unaccountedCount: z.number().int(),
  needsLookCount: z.number().int(),
  /** Unread limit alerts (nav badge). */
  alertBadgeCount: z.number().int(),
  /** Optional parts that could not be read this time (e.g. 'ingest'); the figures that depend on them are zero/empty. */
  degraded: z.array(z.string()),
});
export type DashboardRes = z.infer<typeof DashboardRes>;
export const ReportDailyRes = z.object({
  month: monthKey,
  dayOfMonth: z.number().int(),
  daysInMonth: z.number().int(),
  /** One entry per calendar day (future days are 0). Fixed payments (categories of your recurring rules) are left out. */
  items: z.array(z.object({ day: dateKey, spentMinor: paise })),
  totalMinor: paise,
  /** total ÷ days elapsed (today included), rounded to a paisa. */
  averageMinor: paise,
  /** Display names of the categories that were left out. */
  fixedCategories: z.array(z.string()),
});
export type ReportDailyRes = z.infer<typeof ReportDailyRes>;

/** Month-end pace: flexible spend so far ÷ days elapsed × days in month (₹10), plus the fixed payments. */
export const MonthPace = z.object({
  dayOfMonth: z.number().int(),
  daysInMonth: z.number().int(),
  spentSoFarMinor: paise,
  flexibleSoFarMinor: paise,
  /** Σ committed per month over the fixed categories (Rent, SIP). */
  fixedMinor: paise,
  flexiblePaceMinor: paise,
  /** flexiblePace + fixed: where the month ends at this pace. */
  paceSpentMinor: paise,
  /** income so far − paceSpent. */
  paceKeptMinor: paise,
});
export type MonthPace = z.infer<typeof MonthPace>;

export const ReportMonthItem = z.object({
  month: monthKey,
  incomeMinor: paise,
  spentMinor: paise,
  keptMinor: paise,
  /** kept ÷ income as a fraction (0 when there is no income). */
  keptRate: z.number(),
  /** Balance at the month's end (today's balance for the month in progress). */
  closingMinor: paise,
  inProgress: z.boolean(),
  pace: MonthPace.nullable(),
});
export const ReportMonthsRes = z.object({
  /** Last month of the range = the month in progress. */
  end: monthKey,
  items: z.array(ReportMonthItem),
  averages: z.object({
    /** Finished months with any activity: what the averages are over. */
    fullMonths: z.number().int(),
    avgMonthlySpendMinor: paise,
    avgKeptMinor: paise,
    /** Σ kept ÷ Σ income over the same months. */
    avgKeptRate: z.number(),
    /** Balance today − balance at the end of the first month with activity. */
    balanceSinceMinor: paise,
    balanceSinceMonth: monthKey.nullable(),
  }),
});
export type ReportMonthsRes = z.infer<typeof ReportMonthsRes>;

export const ReportMatrixItem = z.object({
  categoryId: uuid,
  /** Stored lowercase; show with displayTag. */
  name: z.string(),
  byMonth: z.array(z.object({ month: monthKey, spentMinor: paise })),
  /** Average of the finished months. */
  usualMinor: paise,
  spentSoFarMinor: paise,
  /** This month's pace for the category (₹10). */
  paceMinor: paise,
  /** pace − usual; positive = above a usual month. */
  changeMinor: paise,
});
export const ReportMatrixRes = z.object({
  end: monthKey,
  months: z.array(monthKey),
  fullMonths: z.number().int(),
  dayOfMonth: z.number().int(),
  daysInMonth: z.number().int(),
  /** Flexible categories only (categories of your recurring rules that stay the same are left out), most above usual first. */
  items: z.array(ReportMatrixItem),
});
export type ReportMatrixRes = z.infer<typeof ReportMatrixRes>;
