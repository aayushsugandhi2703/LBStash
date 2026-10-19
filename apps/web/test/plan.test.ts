import { describe, expect, it } from 'vitest';
import { addTag, type Draft, draftFrom, lineView, MAX_LINES, planMath, segments, stepLine, stepTotal, suggestions, toPutBody } from '@/features/plan';

const R = (n: number) => n * 100;

// docs/ui-spec/03-plan sample: 50,000 to plan, 45,500 assigned
const sample: Draft = {
  totalMinor: R(50000),
  lines: [
    { categoryId: 'rent', name: 'rent', allocatedMinor: R(20000), spentMinor: R(20000) },
    { categoryId: 'sip', name: 'sip', allocatedMinor: R(10000), spentMinor: R(10000) },
    { categoryId: 'food', name: 'food', allocatedMinor: R(8000), spentMinor: R(5420) },
    { categoryId: 'travel', name: 'travel', allocatedMinor: R(3000), spentMinor: R(1350) },
    { categoryId: 'bills', name: 'bills', allocatedMinor: R(2500), spentMinor: R(1299) },
    { categoryId: 'fun', name: 'fun', allocatedMinor: R(2000), spentMinor: R(1640) },
  ],
};

describe('plan arithmetic', () => {
  it('assigned and unassigned add up to the total', () => {
    expect(planMath(sample)).toEqual({ assigned: R(45500), unassigned: R(4500), over: false, base: R(50000) });
  });
  it('over-assigning is allowed and widens the bar base', () => {
    const m = planMath({ ...sample, totalMinor: R(40000) });
    expect(m).toEqual({ assigned: R(45500), unassigned: R(-5500), over: true, base: R(45500) });
  });
  it('steps the total by 5,000 and a line by 500, never below zero', () => {
    expect(stepTotal(sample, 1).totalMinor).toBe(R(55000));
    expect(stepTotal({ ...sample, totalMinor: R(2000) }, -1).totalMinor).toBe(0);
    expect(stepLine(sample, 2, -1).lines[2]!.allocatedMinor).toBe(R(7500));
    expect(stepLine({ ...sample, lines: [{ ...sample.lines[0]!, allocatedMinor: R(200) }] }, 0, -1).lines[0]!.allocatedMinor).toBe(0);
  });
  it('leaves the other lines untouched when one steps', () => {
    expect(stepLine(sample, 0, 1).lines.slice(1)).toEqual(sample.lines.slice(1));
  });
});

describe('line view', () => {
  it('Food after two presses of minus: 7,000 planned leaves 1,580', () => {
    const food = stepLine(stepLine(sample, 2, -1), 2, -1).lines[2]!;
    expect(lineView(food).remainMinor).toBe(R(1580));
  });
  it('colours the used bar green under 80%, yellow from 80%, red once over', () => {
    expect(lineView(sample.lines[2]!).colour).toBe('accent'); // 67.75%
    expect(lineView(sample.lines[5]!)).toMatchObject({ colour: 'warn', pct: 82 });
    const over = lineView({ ...sample.lines[5]!, spentMinor: R(2300) });
    expect(over).toMatchObject({ colour: 'danger', over: true, pct: 100, remainMinor: R(-300) });
  });
  it('a line with nothing planned reads 0% and not NaN', () => {
    expect(lineView({ name: 'gym', allocatedMinor: 0, spentMinor: 0 }).pct).toBe(0);
  });
});

describe('split bar', () => {
  it('segments are shares of the total and the free tail is the unassigned 9%', () => {
    const { widths, free } = segments(sample);
    expect(widths[0]).toBeCloseTo(40);
    expect(free).toBeCloseTo(9);
    expect(widths.reduce((a, b) => a + b, 0) + free).toBeCloseTo(100);
  });
  it('has no free tail when over-assigned', () => {
    expect(segments({ ...sample, totalMinor: R(40000) }).free).toBe(0);
  });
});

describe('adding a category by typing a tag', () => {
  it('"#Gym" becomes a zero line named gym', () => {
    const r = addTag(sample, '#Gym');
    expect(r.ok && r.added).toBe(true);
    expect(r.ok && r.draft.lines.at(-1)).toEqual({ tag: 'gym', name: 'gym', allocatedMinor: 0, spentMinor: 0 });
  });
  it('does nothing for an empty tag or one already on the plan', () => {
    expect(addTag(sample, ' # ')).toEqual({ ok: true, draft: sample, added: false });
    expect(addTag(sample, '#FOOD')).toEqual({ ok: true, draft: sample, added: false });
  });
  it('refuses a tenth line and an unusable tag in plain words', () => {
    const full: Draft = { ...sample, lines: Array.from({ length: MAX_LINES }, (_, i) => ({ name: `c${i}`, allocatedMinor: 0, spentMinor: 0 })) };
    expect(addTag(full, 'gym')).toEqual({ ok: false, message: `A plan shows up to ${MAX_LINES} categories.` });
    const bad = addTag(sample, '!!!');
    expect(bad.ok).toBe(false);
  });
  it('suggests only the user\'s own categories that are not on the plan', () => {
    expect(suggestions(sample, ['food', 'coffee', 'books'])).toEqual(['coffee', 'books']);
    const withGym = addTag(sample, 'gym');
    expect(suggestions(withGym.ok ? withGym.draft : sample, ['gym'])).toEqual([]);
  });
});

describe('talking to the API', () => {
  it('sends existing categories by id and new ones by tag', () => {
    const withGym = addTag(sample, 'gym');
    const body = toPutBody(withGym.ok ? withGym.draft : sample);
    expect(body.totalMinor).toBe(R(50000));
    expect(body.lines[0]).toEqual({ categoryId: 'rent', allocatedMinor: R(20000) });
    expect(body.lines.at(-1)).toEqual({ tag: 'gym', allocatedMinor: 0 });
  });
  it('turns a plan response back into a draft', () => {
    const d = draftFrom({ totalMinor: 100, lines: [{ categoryId: 'a', categoryName: 'food', allocatedMinor: 60, spentMinor: 10 }] });
    expect(d).toEqual({ totalMinor: 100, lines: [{ categoryId: 'a', name: 'food', allocatedMinor: 60, spentMinor: 10 }] });
  });
});
