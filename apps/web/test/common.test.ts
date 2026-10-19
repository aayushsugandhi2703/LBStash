import { describe, expect, it } from 'vitest';
import {
  addMonths, addMonthsClamped, checkPassword, daysInMonth, formatInr, limitStatus, monthProgress, parseRupees, parseTag, passwordLabel, passwordScore,
} from '@/common';

describe('money', () => {
  it('formats with Indian grouping', () => {
    expect(formatInr(3759100)).toBe('37,591');
    expect(formatInr(123456789000)).toBe('1,23,45,67,890');
    expect(formatInr(45050)).toBe('450.50');
    expect(formatInr(-120000, { symbol: true })).toBe('-₹1,200');
    expect(formatInr(0)).toBe('0');
  });
  it('parses rupees to paise', () => {
    expect(parseRupees('450')).toBe(45000);
    expect(parseRupees('₹1,234.5')).toBe(123450);
    expect(parseRupees('Rs. 99.05')).toBe(9905);
    expect(() => parseRupees('12.345')).toThrow();
    expect(() => parseRupees('abc')).toThrow();
  });
});

describe('time (Asia/Kolkata)', () => {
  it('progress, days and month math', () => {
    const p = monthProgress(new Date('2026-10-18T10:00:00+05:30'), 'Asia/Kolkata');
    expect(p).toEqual({ month: '2026-10', day: 18, days: 31, daysLeft: 14 });
    expect(monthProgress(new Date('2026-09-30T20:00:00Z'), 'Asia/Kolkata').month).toBe('2026-10');
    expect(monthProgress(new Date('2026-09-30T20:00:00Z'), 'UTC').month).toBe('2026-09');
    expect(daysInMonth('2028-02')).toBe(29);
    expect(addMonths('2026-11', 3)).toBe('2027-02');
    expect(addMonths('2026-01', -1)).toBe('2025-12');
    expect(addMonthsClamped('2026-01-31', 1, 31)).toBe('2026-02-28');
    expect(addMonthsClamped('2026-02-28', 1, 31)).toBe('2026-03-31');
  });
});

describe('limit status', () => {
  it('follows the alert level and the pace', () => {
    expect(limitStatus({ spent: 8200, limit: 10000, alertPct: 80, projected: 15000 })).toBe('close');
    expect(limitStatus({ spent: 7999, limit: 10000, alertPct: 80, projected: 9000 })).toBe('ok');
    expect(limitStatus({ spent: 5000, limit: 10000, alertPct: 80, projected: 12000 })).toBe('fast');
    expect(limitStatus({ spent: 10000, limit: 10000, alertPct: 80, projected: 12000 })).toBe('over');
  });
});

describe('tags and password policy', () => {
  it('normalises tags', () => {
    expect(parseTag('  #Bank   Charges ')).toEqual({ ok: true, tag: 'bank charges' });
    expect(parseTag('#').ok).toBe(false);
    expect(parseTag('a'.repeat(33)).ok).toBe(false);
  });
  it('password score follows the design', () => {
    const c = checkPassword('abc', 'a@b.co');
    expect(passwordLabel(passwordScore('abc', c))).toBe('weak');
    const ok = checkPassword('correct-horse-battery', 'sam@example.com');
    expect(passwordLabel(passwordScore('correct-horse-battery', ok))).toBe('strong');
    expect(checkPassword('mysamword12345', 'sam@example.com').email).toBe(false);
    expect(checkPassword('password1234').common).toBe(false);
  });
});
