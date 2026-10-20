import { z } from 'zod';
import { CategoryDto, isoDateTime, monthKey, paise, TransactionDto, uuid } from './common';

export const TransactionRes = z.object({ transaction: TransactionDto });

export const TransactionSettings = z.object({
  openingBalanceMinor: paise,
  /** Hours the balance check waits before booking an Unaccounted entry (default 6). */
  reconcileGraceHours: z.number().int().min(0).max(72),
});
export type TransactionSettings = z.infer<typeof TransactionSettings>;

/** Row of the Transactions list: the transaction plus how it got its category (for "matched rule: uber" / "same payee as last month"). */
export const TransactionRowDto = TransactionDto.extend({
  classifiedBy: z.enum(['memory', 'rule', 'user', 'recurring']).nullable(),
  /** The keyword that matched, when classifiedBy is 'rule'. */
  matchedRule: z.string().nullable(),
});
export type TransactionRowDto = z.infer<typeof TransactionRowDto>;

/** One entry of the category index: entries in scope, and money out / in (excluding #transfer and reversed). */
export const CategoryStatDto = z.object({
  categoryId: uuid, categoryName: z.string(), archived: z.boolean(),
  count: z.number().int(), spentMinor: paise, receivedMinor: paise,
});
export const TransactionCountsDto = z.object({
  all: z.number().int(), needsTag: z.number().int(), unaccounted: z.number().int(),
  byCategory: z.array(CategoryStatDto),
});
export const TransactionPageDto = z.object({
  month: monthKey.nullable(),
  items: z.array(TransactionRowDto),
  nextCursor: z.string().nullable(),
  /** Entries matching every filter ("showing {items} of {matching}"). */
  matching: z.number().int(),
  counts: TransactionCountsDto,
  /** "the transactions says ₹37,591" */
  balanceMinor: paise,
});
export type TransactionPageDto = z.infer<typeof TransactionPageDto>;
export const CreditRes = z.object({
  transaction: TransactionDto,
  categoryCreated: z.boolean(),
  /** Balance after the credit. */
  balanceMinor: paise,
  /** The month's plan total after adding; null if not added or planning was unreachable (`credit.added` catches up). */
  planTotalMinor: paise.nullable(),
});
export const CreditsRes = z.object({ items: z.array(TransactionDto), balanceMinor: paise });

export const CategoryUsageDto = CategoryDto.extend({ count: z.number().int() });
export const CategoriesUsageRes = z.object({ items: z.array(CategoryUsageDto) });

export const BalanceCheckStatus = z.enum(['open', 'booked', 'resolved', 'ignored']);
export const BalanceCheckDto = z.object({
  id: uuid,
  bankBalanceMinor: paise,
  transactionsBalanceMinor: paise,
  /** bank − transactions: negative = the bank is lower (money left that no message explains). */
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
  /** True when the gap is under ₹1 ("matches the transactions"). */
  matches: z.boolean(),
  /** Transactions balance right now. */
  transactionsBalanceMinor: paise,
  transaction: TransactionDto.nullable(),
});
export const BalanceChecksRes = z.object({ items: z.array(BalanceCheckDto) });
