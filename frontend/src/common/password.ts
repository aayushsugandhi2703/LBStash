/** Mirrors the auth service's password rules (12+ characters, not common, no email name) so the live meter matches the server. */
const MIN_PASSWORD_LENGTH = 12;

const COMMON = new Set([
  'password1234', '123456789012', 'qwertyuiop12', 'iloveyou1234', 'passwordpassword', 'password12345',
  'welcome12345', 'letmein12345', 'administrator', 'qwertyuiopas', 'abcdefghijkl', '111111111111',
  '1234567890123', '12345678901234', 'changeme1234', 'iloveyou12345', 'trustno1trustno1',
]);

interface PasswordChecks { len: boolean; common: boolean; email: boolean }

export function checkPassword(password: string, email = ''): PasswordChecks {
  const pw = password.toLowerCase();
  const local = (email.split('@')[0] ?? '').toLowerCase();
  return {
    len: password.length >= MIN_PASSWORD_LENGTH,
    common: password.length > 0 && !COMMON.has(pw),
    email: password.length > 0 && !(local.length >= 3 && pw.includes(local)),
  };
}

/** 0 to 4. Under 12 characters is at most 1 ("weak"). */
export function passwordScore(password: string, c: PasswordChecks): number {
  if (!c.len) return password ? 1 : 0;
  return 1 + (c.common ? 1 : 0) + (c.email ? 1 : 0) + (password.length >= 16 ? 1 : 0);
}

export const passwordLabel = (score: number): '' | 'weak' | 'okay' | 'strong' =>
  score === 0 ? '' : score <= 1 ? 'weak' : score === 2 ? 'okay' : 'strong';
