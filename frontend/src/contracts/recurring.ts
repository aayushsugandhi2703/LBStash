import { z } from 'zod';
import { dateKey, paise, positivePaise, uuid } from './common';


/** RECURRING SERVICE. */
export const Schedule = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('monthly'), day: z.number().int().min(1).max(31) }),
  z.object({ kind: z.literal('weekly'), weekday: z.number().int().min(0).max(6) }),
  z.object({ kind: z.literal('yearly'), month: z.number().int().min(1).max(12), day: z.number().int().min(1).max(31) }),
]);
export type Schedule = z.infer<typeof Schedule>;

export const RecurringRuleDto = z.object({
  id: uuid, name: z.string(), categoryId: uuid, categoryName: z.string(), amountMinor: positivePaise,
  schedule: Schedule, nextDue: dateKey, paused: z.boolean(), endsOn: dateKey.nullable(),
  /** Short line under the name on the Repeats page ("to landlord"). */
  note: z.string().nullable().default(null),
  /** Payee or keyword used to link an already-captured debit within ±2 days of the due date. */
  matchHint: z.string().nullable().default(null),
  /** Counts toward `committedMinor`: not paused and not past its end date. */
  active: z.boolean().default(true),
});
export type RecurringRuleDto = z.infer<typeof RecurringRuleDto>;
/** `GET /recurring` (public and internal). `committedMinor` = sum over active rules, per month. */
export const RecurringRes = z.object({ items: z.array(RecurringRuleDto), committedMinor: paise });

const RuleName = z.string().trim().min(1).max(80);
const RuleNote = z.string().trim().max(120).nullable();
const RuleHint = z.string().trim().min(1).max(100).nullable();
const eitherTagOrId = (v: { categoryId?: string; tag?: string }) => !(v.categoryId && v.tag);

/** `POST /recurring`. Give `categoryId` or a new `tag`. `startsOn` defaults to today, never in the past. */
export const CreateRecurringReq = z.object({
  name: RuleName,
  categoryId: uuid.optional(),
  tag: z.string().min(1).max(64).optional(),
  amountMinor: positivePaise,
  schedule: Schedule,
  startsOn: dateKey.optional(),
  endsOn: dateKey.nullable().optional(),
  matchHint: RuleHint.optional(),
  note: RuleNote.optional(),
}).refine((v) => Boolean(v.categoryId) !== Boolean(v.tag), 'give either categoryId or tag');
export type CreateRecurringReq = z.infer<typeof CreateRecurringReq>;

/** `PATCH /recurring/:id`. */
export const PatchRecurringReq = z.object({
  name: RuleName,
  categoryId: uuid,
  tag: z.string().min(1).max(64),
  amountMinor: positivePaise,
  schedule: Schedule,
  endsOn: dateKey.nullable(),
  matchHint: RuleHint,
  note: RuleNote,
  paused: z.boolean(),
  skipNext: z.literal(true),
}).partial().refine((v) => Object.keys(v).length > 0, 'nothing to change').refine(eitherTagOrId, 'give either categoryId or tag');
export type PatchRecurringReq = z.infer<typeof PatchRecurringReq>;
