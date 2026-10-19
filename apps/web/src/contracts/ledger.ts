import { z } from 'zod';
import { CategoryDto, isoDateTime, monthKey, paise, TransactionDto, uuid } from './common';

export const TransactionRes = z.object({ transaction: TransactionDto });

export const LedgerSettings = z.object({
  openingBalanceMinor: paise,
  /** Hours the balance check waits before booking an Unaccounted entry (default 6). */
  reconcileGraceHours: z.number().int().min(0).max(72),
});
export type LedgerSettings = z.infer<typeof LedgerSettings>;

/** Row of the Ledger list: the transaction plus how it got its category (for "matched rule: uber" / "same payee as last month"). */
export const LedgerRowDto = TransactionDto.extend({
  classifiedBy: z.enum(['memory', 'rule', 'user', 'recurring']).nullable(),
  /** The keyword that matched, when classifiedBy is 'rule'. */
  matchedRule: z.string().nullable(),
});
export type LedgerRowDto = z.infer<typeof LedgerRowDto>;

/** One entry of the category index: entries in scope, and money out / in (excluding #transfer and reversed). */
export const CategoryStatDto = z.object({
  categoryId: uuid, categoryName: z.string(), archived: z.boolean(),
  count: z.number().int(), spentMinor: paise, receivedMinor: paise,
});
export const LedgerCountsDto = z.object({
  all: z.number().int(), needsTag: z.number().int(), unaccounted: z.number().int(),
  byCategory: z.array(CategoryStatDto),
});
export const LedgerPageDto = z.object({
  month: monthKey.nullable(),
  items: z.array(LedgerRowDto),
  nextCursor: z.string().nullable(),
  /** Entries matching every filter ("showing {items} of {matching}"). */
  matching: z.number().int(),
  counts: LedgerCountsDto,
  /** "the ledger says ₹37,591" */
  balanceMinor: paise,
});
export type LedgerPageDto = z.infer<typeof LedgerPageDto>;
export const CreditRes = z.object({
  transaction: TransactionDto,
  categoryCreated: z.boolean(),
  /** Balance after the credit. */
  balanceMinor: paise,
  /** The month's plan total after adding it; null when not added or planning could not be reached (the credit.added event catches up). */
  planTotalMinor: paise.nullable(),
});
export const CreditsRes = z.object({ items: z.array(TransactionDto), balanceMinor: paise });

export const CategoryUsageDto = CategoryDto.extend({ count: z.number().int() });
export const CategoriesUsageRes = z.object({ items: z.array(CategoryUsageDto) });

export const BalanceCheckStatus = z.enum(['open', 'booked', 'resolved', 'ignored']);
export const BalanceCheckDto = z.object({
  id: uuid,
  bankBalanceMinor: paise,
  ledgerBalanceMinor: paise,
  /** bank − ledger: negative = the bank is lower (money left that no message explains). */
  gapMinor: paise,
  source: z.enum(['message', 'manual']),
  status: BalanceCheckStatus,
  checkedAt: isoDateTime,
  /** The moment the bank balance refers to. */
  asOf: isoDateTime,
  /** The Unaccounted entry it booked. */
  transactionId: uuid.nullable(),
  /** While open: when the Unaccounted entry gets booked unless a message closes the gap first. */
  graceEndsAt: isoDateTime.nullable(),
});
export type BalanceCheckDto = z.infer<typeof BalanceCheckDto>;
export const BalanceCheckRes = z.object({
  check: BalanceCheckDto,
  /** True when the gap is under ₹1 ("matches the ledger"). */
  matches: z.boolean(),
  /** Ledger balance right now. */
  ledgerBalanceMinor: paise,
  transaction: TransactionDto.nullable(),
});
export const BalanceChecksRes = z.object({ items: z.array(BalanceCheckDto) });
