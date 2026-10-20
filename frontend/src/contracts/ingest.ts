import { z } from 'zod';
import { isoDateTime, paise, positivePaise, TxType, uuid } from './common';
import { TransactionRes } from './transactions';


export const DeviceDto = z.object({
  id: uuid, name: z.string(), lastSeenAt: isoDateTime.nullable(), revokedAt: isoDateTime.nullable(), createdAt: isoDateTime,
  /** Masked token for display, for example `ledg_live_8f3a…b605`. The token itself is never readable again. */
  tokenHint: z.string(),
  /** When the token was last replaced (null = never rotated). */
  rotatedAt: isoDateTime.nullable(),
  /** Seconds between the time written in the last message and the moment the sender ran (null when unknown). */
  lastDelaySeconds: z.number().int().nullable(),
  /** Empty list = every sender is accepted. */
  allowedSenders: z.array(z.string()),
  /** The latest test message (from the phone or from the Devices page), for the live test status. */
  lastTest: z.object({ at: isoDateTime, source: z.enum(['device', 'web']), delaySeconds: z.number().int().nullable(), amountMinor: paise.nullable() }).nullable(),
});
export type DeviceDto = z.infer<typeof DeviceDto>;
/** The only time the token is shown. */
export const DeviceTokenRes = z.object({ device: DeviceDto, token: z.string(), rotated: z.boolean() });

/** One "Needs a look" message. `text` is the user's own message (masked), decrypted only for this response. */
export const UnparsedDto = z.object({
  id: uuid,
  receivedAt: isoDateTime,
  expiresAt: isoDateTime,
  reason: z.enum(['no_amount', 'direction_unclear', 'unreadable']),
  text: z.string(),
  /** What the parser could still guess, to prefill the form. */
  suggestion: z.object({ type: TxType.nullable(), amountMinor: positivePaise.nullable(), payee: z.string().nullable() }),
});
export const UnparsedRes = z.object({ items: z.array(UnparsedDto), open: z.number().int() });
export const ResolveUnparsedRes = z.object({ transaction: TransactionRes.shape.transaction, open: z.number().int() });
export const DismissUnparsedRes = z.object({ ok: z.literal(true), open: z.number().int() });
