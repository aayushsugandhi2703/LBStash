import { describe, expect, it } from 'vitest';
import { addRupees, cleanAmount, fromPaise, groupIndian, reformat, toPaise } from '@/common';

describe('amount typing', () => {
  it('strips everything that is not a digit, like the credit spec example 5x0,000', () => {
    expect(cleanAmount('5x0,000')).toBe('50000');
    expect(groupIndian(cleanAmount('5x0,000'))).toBe('50,000');
  });
  it('drops leading zeros and shows nothing for 0', () => {
    expect(cleanAmount('0')).toBe('');
    expect(cleanAmount('007')).toBe('7');
  });
  it('keeps at most 9 digits', () => {
    expect(cleanAmount('1234567890123')).toBe('123456789');
  });
  it('groups the Indian way', () => {
    expect(groupIndian('1')).toBe('1');
    expect(groupIndian('1250')).toBe('1,250');
    expect(groupIndian('51000')).toBe('51,000');
    expect(groupIndian('100000')).toBe('1,00,000');
    expect(groupIndian('12345678')).toBe('1,23,45,678');
  });
  it('allows two decimals only when asked, and keeps a lone point so typing can continue', () => {
    expect(cleanAmount('12.345')).toBe('12345');
    expect(cleanAmount('12.345', { decimals: true })).toBe('12.34');
    expect(cleanAmount('.5', { decimals: true })).toBe('0.5');
    expect(groupIndian(cleanAmount('1234.', { decimals: true }))).toBe('1,234.');
    expect(cleanAmount('1.2.3', { decimals: true })).toBe('1.23');
  });
  it('keeps the caret next to its digit when grouping changes', () => {
    // "1,250" with a 0 typed after the 5 → raw "1,2500", caret at the end
    const r = reformat('1,2500', 6);
    expect(r.display).toBe('12,500');
    expect(r.caret).toBe(6);
    // typing a digit in the middle: "12,500" → insert 9 after the "1"
    const m = reformat('192,500', 2);
    expect(m.display).toBe('1,92,500');
    expect(m.caret).toBe(3);
  });
  it('puts the caret at the start when the leading digit is deleted from nothing', () => {
    expect(reformat('', 0)).toEqual({ value: '', display: '', caret: 0 });
  });
});

describe('rupees and paise', () => {
  it('converts boxes to paise', () => {
    expect(toPaise('')).toBe(0);
    expect(toPaise('1250')).toBe(125_000);
    expect(toPaise('1250.5')).toBe(125_050);
    expect(toPaise('0.05')).toBe(5);
  });
  it('converts paise back to the box text', () => {
    expect(fromPaise(125_000)).toBe('1250');
    expect(fromPaise(125_050)).toBe('1250.5');
    expect(fromPaise(125_005)).toBe('1250.05');
    expect(fromPaise(0)).toBe('');
  });
  it('adds quick amounts: 5x0,000 then + 1,000 is 51,000, and it never passes the digit limit', () => {
    expect(addRupees('50000', 1000)).toBe('51000');
    expect(addRupees('', 5000)).toBe('5000');
    expect(addRupees('999999000', 5000)).toBe('999999999');
  });
});
