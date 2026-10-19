import { z } from 'zod';


/** Shared building blocks. Money is integer paise; times are ISO strings; days are 'YYYY-MM-DD'. */
export const uuid = z.uuid();
export const paise = z.number().int().safe();
export const positivePaise = paise.positive();
export const isoDateTime = z.iso.datetime({ offset: true });
export const dateKey = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'YYYY-MM-DD');
export const monthKey = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/, 'YYYY-MM');
export const tzName = z.string().min(1).max(64);

export const TxType = z.enum(['debit', 'credit']);
export const TxSource = z.enum(['captured', 'recurring', 'manual', 'unaccounted']);
export const TxStatus = z.enum(['pending', 'confirmed', 'reversed']);
export type TxType = z.infer<typeof TxType>;
export type TxSource = z.infer<typeof TxSource>;
export type TxStatus = z.infer<typeof TxStatus>;

export const TransactionDto = z.object({
  id: uuid,
  type: TxType,
  amountMinor: positivePaise,
  /** When the payment happened (read from the bank message when there is one). */
  occurredAt: isoDateTime,
  payee: z.string().nullable(),
  description: z.string().nullable(),
  categoryId: uuid.nullable(),
  categoryName: z.string().nullable(),
  source: TxSource,
  status: TxStatus,
  recurringId: uuid.nullable(),
  /** When the Shortcut delivered it (captured rows only). */
  capturedAt: isoDateTime.nullable(),
  /** Amount and direction were read but nothing else (README 4.7). */
  weakParse: z.boolean(),
});
export type TransactionDto = z.infer<typeof TransactionDto>;

export const CategoryDto = z.object({
  id: uuid,
  /** Stored lowercase; show with `displayTag`. */
  name: z.string(),
  archived: z.boolean(),
});
export type CategoryDto = z.infer<typeof CategoryDto>;

/** `GET /internal/export` on every data service: that service's rows for the token's user, secrets left out (no token hashes, no encrypted fields, no password hashes). */
export const ExportPart = z.object({
  service: z.string(),
  tables: z.record(z.string(), z.array(z.record(z.string(), z.unknown()))),
});
export type ExportPart = z.infer<typeof ExportPart>;
