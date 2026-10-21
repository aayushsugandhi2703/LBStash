import { z } from 'zod';
import { TransactionSettings } from './transactions';
import { PlanningSettings } from './planning';
import { TelegramSettings } from './telegram';


/** `GET|PATCH /settings` is composed by the gateway. */
export const SettingsDto = TransactionSettings.extend(PlanningSettings.shape).extend(TelegramSettings.shape).extend({ currency: z.literal('INR') });
export type SettingsDto = z.infer<typeof SettingsDto>;

/** `GET /me`: what the shared header needs. Composed by the gateway. */
export const MeDto = z.object({
  id: z.string(), email: z.string(), name: z.string().nullable(), timezone: z.string(),
  pendingEmail: z.string().nullable(), deleteAfter: z.string().nullable(),
  /** unread limit alerts + messages that need a look, for the nav badge and the Account menu */
  alertBadgeCount: z.number().int(), needsLookCount: z.number().int(), untaggedCount: z.number().int(),
  /** true only for the sample-data demo account (read-only) */
  demo: z.boolean().default(false),
});
