import { describe, expect, it } from 'vitest';
import { ApiError } from '@/lib/api';
import { codeError, waitText } from '@/features/account';

describe('second-step errors (sign-in, ui-spec 12)', () => {
  it('counts the tries left', () => {
    expect(codeError(new ApiError(401, 'two_factor_invalid', 'x', { attemptsLeft: 2 }))).toBe('That code did not work. 2 tries left.');
    expect(codeError(new ApiError(401, 'two_factor_invalid', 'x', { attemptsLeft: 1 }))).toBe('That code did not work. 1 try left.');
    expect(codeError(new ApiError(401, 'two_factor_invalid', 'x', { attemptsLeft: 0 }))).toBe('Too many tries. Wait a minute, then try again.');
  });
  it('says how long a lockout lasts', () => {
    expect(codeError(new ApiError(423, 'locked', 'x', { retryAfterSeconds: 900 }))).toBe('Too many tries. Try again in 15 minutes.');
    expect(waitText(30)).toBe('30 seconds');
    expect(waitText(61)).toBe('2 minutes');
  });
  it('leaves other errors to the caller', () => {
    expect(codeError(new ApiError(500, 'internal', 'x'))).toBeNull();
    expect(codeError(null)).toBeNull();
  });
});
