import { z } from 'zod';
import { monthKey, paise, uuid } from './common';


/** PLANNING SERVICE. */
export const PlanLineDto = z.object({ categoryId: uuid, categoryName: z.string(), allocatedMinor: paise });
export const PlanDto = z.object({ month: monthKey, totalMinor: paise, lines: z.array(PlanLineDto) });
export type PlanDto = z.infer<typeof PlanDto>;

/** `GET /plans/:month` (public and internal): plan with spend per line filled in from the transactions. */
export const PlanWithSpendDto = PlanDto.extend({
  lines: z.array(PlanLineDto.extend({ spentMinor: paise })),
  assignedMinor: paise,
  unassignedMinor: paise,
});

export const LimitStatus = z.enum(['ok', 'fast', 'close', 'over']);
export const BudgetDto = z.object({
  id: uuid, categoryId: uuid, categoryName: z.string(), limitMinor: paise, period: z.literal('monthly'),
  warnPct: z.number().int().min(50).max(99).nullable(), active: z.boolean(),
  spentMinor: paise, pct: z.number().int(), projectedMinor: paise, status: LimitStatus,
});
export type BudgetDto = z.infer<typeof BudgetDto>;
/** `GET /budgets?month=` */
export const BudgetsRes = z.object({ month: monthKey, alertLevel: z.number().int(), items: z.array(BudgetDto) });

export const AlertDto = z.object({
  id: uuid, budgetId: uuid, categoryName: z.string(), level: z.enum(['alert', 'exceeded']), periodKey: z.string(),
  sentAt: z.string(), readAt: z.string().nullable(),
});
export const AlertsRes = z.object({ unreadCount: z.number().int(), items: z.array(AlertDto) });

export const PlanningSettings = z.object({
  /** 70, 80 or 90 (default 80). */
  alertLevel: z.union([z.literal(70), z.literal(80), z.literal(90)]),
  warnOnPace: z.boolean(),
});
export type PlanningSettings = z.infer<typeof PlanningSettings>;

/** One plan line in `PUT /plans/:month`: the category by id, or by a (possibly new) tag. Exactly one of the two. */
export const PlanLineInput = z.object({
  categoryId: uuid.optional(),
  tag: z.string().min(1).max(64).optional(),
  allocatedMinor: paise.min(0),
}).refine((l) => (l.categoryId === undefined) !== (l.tag === undefined), { message: 'Give either categoryId or tag', path: ['categoryId'] });
/** `PUT /plans/:month`: replaces the total and every line (the response is the new PlanWithSpendDto). */
export const PlanPutReq = z.object({ totalMinor: paise.min(0), lines: z.array(PlanLineInput).max(100) });
export type PlanPutReq = z.infer<typeof PlanPutReq>;
