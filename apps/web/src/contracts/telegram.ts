import { z } from 'zod';
import { isoDateTime } from './common';


/** TELEGRAM SERVICE. */
export const TelegramSettings = z.object({
  allowReveal: z.boolean(),
  sessionIdleDays: z.number().int().min(1).max(90),
  /** Daily reminder of untagged payments: Off / Daily / Twice a day (the second goes out 12 hours after `digestHour`). */
  digestMode: z.enum(['off', 'daily', 'twice']),
  /** Local hour of the (first) reminder, 0-23 (default 21 = "Daily, 9 pm"). */
  digestHour: z.number().int().min(0).max(23),
  /** After you tag: keep the message (no buttons), collapse it to one line, or delete it. */
  afterTag: z.enum(['keep', 'line', 'delete']),
});
export type TelegramSettings = z.infer<typeof TelegramSettings>;

/** `GET /telegram/link`: everything the Setup guide (steps 2 and 3) and the Devices page show. */
export const TelegramLinkStatus = z.object({
  botSaved: z.boolean(),
  botUsername: z.string().nullable(),
  /** Telegram account allowed to link ("@name" or numeric id); codes need it set first. */
  ownerTelegram: z.string().nullable(),
  linked: z.boolean(),
  /** "••4821": the last four digits of the Telegram id, never the whole id. */
  telegramIdHint: z.string().nullable(),
  telegramUsername: z.string().nullable(),
  linkedAt: isoDateTime.nullable(),
  sessionActive: z.boolean(),
  /** When the current bot session started (null when signed out). */
  sessionSince: isoDateTime.nullable(),
  lastSeenAt: isoDateTime.nullable(),
  /** Set while sign-in is paused after three wrong codes. */
  signInPausedUntil: isoDateTime.nullable(),
  /** A pairing code is valid; the Setup guide polls until `linked`. */
  pairingPending: z.boolean(),
  /** Prompts waiting for `/signin`. */
  heldCount: z.number().int(),
});
export type TelegramLinkStatus = z.infer<typeof TelegramLinkStatus>;

/** `POST /telegram/pairing`: shown once; only a hash is stored. `command` is what the user sends to the bot. */
export const PairingRes = z.object({ code: z.string(), command: z.string(), expiresAt: isoDateTime });
export type PairingRes = z.infer<typeof PairingRes>;
