import { z } from 'zod';
import { ExportPart, isoDateTime, tzName, uuid } from './common';


/** AUTH SERVICE. */
export const UserDto = z.object({
  id: uuid, email: z.string(), name: z.string().nullable(), timezone: tzName,
  pendingEmail: z.string().nullable(), deleteAfter: z.string().nullable(),
  /** ISO time the account was created ("member since"). */
  createdAt: z.string().optional(),
});
export type UserDto = z.infer<typeof UserDto>;

export const AuthMethod = z.enum(['totp', 'passkey', 'recovery']);
export type AuthMethod = z.infer<typeof AuthMethod>;

/** Mandatory setup: authenticator enabled AND a recovery set made. Until `complete`, the session is setup-limited. */
export const SetupState = z.object({ totpEnabled: z.boolean(), recoveryCodes: z.boolean(), complete: z.boolean() });
export type SetupState = z.infer<typeof SetupState>;

/** Answer of every call that starts or renews a browser session (register, 2fa/verify, passkey login, refresh). */
export const AuthSessionRes = z.object({
  user: UserDto,
  setup: SetupState,
  recoveryCodesLeft: z.number().int(),
  /** A recovery code was used to sign in: ask the user to make a fresh set. */
  recoveryCodeUsed: z.boolean(),
  /** Signing in cancelled a scheduled account deletion. */
  deletionCancelled: z.boolean(),
});
export type AuthSessionRes = z.infer<typeof AuthSessionRes>;
/** Step 1 of sign-in. `setupRequired` means the account never finished setup and `twoFactorToken` is null. */
export const LoginRes = z.object({
  twoFactorToken: z.string().nullable(),
  methods: z.array(AuthMethod),
  setupRequired: z.boolean(),
  setup: SetupState.nullable(),
});
/** `secret` is the base32 key to type in; `otpauthUri` is what the QR code encodes. */
export const TwoFactorEnableStartRes = z.object({ secret: z.string(), otpauthUri: z.string() });
export const TwoFactorEnableConfirmRes = z.object({ setup: SetupState });
export const RecoveryCodesRes = z.object({ codes: z.array(z.string()), remaining: z.number().int(), setup: SetupState });

export const PasskeyDto = z.object({ id: uuid, label: z.string(), createdAt: z.string(), lastUsedAt: z.string().nullable() });
export type PasskeyDto = z.infer<typeof PasskeyDto>;
export const FactorsRes = z.object({
  totp: z.object({ enabled: z.boolean(), since: z.string().nullable() }),
  passkeys: z.array(PasskeyDto),
  recoveryCodes: z.object({ remaining: z.number().int(), total: z.number().int() }),
  passwordChangedAt: z.string(),
  setup: SetupState,
});

export const SessionDto = z.object({
  id: uuid, device: z.string(), ip: z.string().nullable(), createdAt: z.string(), lastActiveAt: z.string(), current: z.boolean(),
});
export type SessionDto = z.infer<typeof SessionDto>;
export const SessionsRes = z.object({ sessions: z.array(SessionDto) });
export const AuditEntryDto = z.object({
  id: z.number().int(), at: z.string(), action: z.string(), ip: z.string().nullable(), deviceId: uuid.nullable(),
  meta: z.record(z.string(), z.unknown()).nullable(),
});
export const AuditRes = z.object({ entries: z.array(AuditEntryDto) });
export const ConfirmEmailRes = z.object({ user: UserDto });
/** `parts[0]` is auth's own part; then ledger, planning, recurring, ingest, telegram. Secrets are never included. */
export const ExportRes = z.object({ exportedAt: isoDateTime, filename: z.string(), entries: z.number().int(), parts: z.array(ExportPart) });
