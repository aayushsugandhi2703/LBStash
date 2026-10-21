import { describe, expect, it } from 'vitest';
import type { RecurringRuleDto } from '@/contracts';
import { committedRows, committedTotal, createBody, dateLabel, dayAfterNext, daysBetween, emptyForm, formErrorsFrom, formFrom, isEnded, isOn, nextRule, nextText, occurrences, patchBody, rangeText, scheduleSentence, scheduleText, stems, ticks, timelineLabel, withoutRule, withRule } from '@/features/repeats';

// ui-spec dataset: October 2026, day 18 (a Sunday); Rent, Nifty 50, Cloud storage and Netflix commit ₹30,779 a month
const TODAY = '2026-10-18';
let n = 0;
const rule = (o: Partial<RecurringRuleDto> & Pick<RecurringRuleDto, 'name' | 'amountMinor' | 'schedule' | 'nextDue'>): RecurringRuleDto => ({
  id: `r${++n}`, categoryId: 'c', categoryName: o.name.toLowerCase(), paused: false, endsOn: null, note: null, matchHint: null, active: true, ...o,
});
const rent = () => rule({ name: 'Rent', amountMinor: 2_000_000, schedule: { kind: 'monthly', day: 1 }, nextDue: '2026-11-01', note: 'to landlord' });
const nifty = () => rule({ name: 'Nifty 50 index fund', amountMinor: 1_000_000, schedule: { kind: 'monthly', day: 5 }, nextDue: '2026-11-05' });
const cloud = () => rule({ name: 'Cloud storage', amountMinor: 13_000, schedule: { kind: 'monthly', day: 12 }, nextDue: '2026-11-12' });
const netflix = () => rule({ name: 'Netflix', amountMinor: 64_900, schedule: { kind: 'monthly', day: 17 }, nextDue: '2026-11-17' });
const sample = () => [rent(), nifty(), cloud(), netflix()];

describe('schedule text', () => {
  it('monthly uses ordinals, including the teens', () => {
    const t = (day: number) => scheduleText({ kind: 'monthly', day });
    expect([t(1), t(2), t(3), t(4), t(11), t(12), t(13), t(21), t(22), t(23), t(31)]).toEqual([
      'monthly · 1st', 'monthly · 2nd', 'monthly · 3rd', 'monthly · 4th', 'monthly · 11th', 'monthly · 12th', 'monthly · 13th', 'monthly · 21st', 'monthly · 22nd', 'monthly · 23rd', 'monthly · 31st',
    ]);
  });
  it('weekly names the day (0 is Sunday) and yearly the month', () => {
    expect(scheduleText({ kind: 'weekly', weekday: 1 })).toBe('weekly · Monday');
    expect(scheduleText({ kind: 'weekly', weekday: 0 })).toBe('weekly · Sunday');
    expect(scheduleText({ kind: 'yearly', month: 3, day: 5 })).toBe('yearly · 5 Mar');
  });
  it('sentences', () => {
    expect(scheduleSentence({ kind: 'monthly', day: 5 })).toBe('monthly on the 5th');
    expect(scheduleSentence({ kind: 'weekly', weekday: 1 })).toBe('weekly on Mondays');
    expect(scheduleSentence({ kind: 'yearly', month: 3, day: 5 })).toBe('yearly on 5 March');
  });
});

describe('dates', () => {
  it('labels and day counts ignore time zones', () => {
    expect(dateLabel('2026-11-01')).toBe('NOV 01');
    expect(daysBetween(TODAY, '2026-11-17')).toBe(30);
    expect(rangeText(TODAY)).toBe('oct 18 to nov 17');
  });
});

describe('occurrences', () => {
  it('a monthly rule shows once in 30 days', () => {
    expect(occurrences(rent(), TODAY)).toEqual(['2026-11-01']);
  });
  it('a weekly rule shows up to five times', () => {
    const r = rule({ name: 'Maid', amountMinor: 50_000, schedule: { kind: 'weekly', weekday: 1 }, nextDue: '2026-10-19' });
    expect(occurrences(r, TODAY)).toEqual(['2026-10-19', '2026-10-26', '2026-11-02', '2026-11-09', '2026-11-16']);
  });
  it('a 31st counts from the wanted day, never from the previous due date (Jan 31, Feb 28, Mar 31)', () => {
    const r = rule({ name: 'Loan', amountMinor: 100_000, schedule: { kind: 'monthly', day: 31 }, nextDue: '2026-01-31' });
    expect(occurrences(r, '2026-01-31', 60)).toEqual(['2026-01-31', '2026-02-28', '2026-03-31']);
  });
  it('a yearly rule repeats a year later and clamps Feb 29', () => {
    const r = rule({ name: 'Insurance', amountMinor: 900_000, schedule: { kind: 'yearly', month: 11, day: 5 }, nextDue: '2026-11-05' });
    expect(occurrences(r, TODAY)).toEqual(['2026-11-05']);
    expect(occurrences(r, TODAY, 400)).toEqual(['2026-11-05', '2027-11-05']);
    const leap = rule({ name: 'Leap', amountMinor: 100, schedule: { kind: 'yearly', month: 2, day: 29 }, nextDue: '2028-02-29' });
    expect(occurrences(leap, '2028-02-29', 800)).toEqual(['2028-02-29', '2029-02-28', '2030-02-28']);
  });
  it('stops at the end date', () => {
    const r = rule({ name: 'Course', amountMinor: 100, schedule: { kind: 'monthly', day: 1 }, nextDue: '2026-11-01', endsOn: '2026-11-15' });
    expect(occurrences(r, TODAY, 90)).toEqual(['2026-11-01']);
  });
  it('a due day before today is not shown', () => {
    const r = rule({ name: 'Old', amountMinor: 100, schedule: { kind: 'monthly', day: 1 }, nextDue: '2026-10-01' });
    expect(occurrences(r, TODAY)).toEqual(['2026-11-01']);
  });
});

describe('timeline stems (spec: Rent 68%, Nifty 34%, Cloud and Netflix stubs)', () => {
  const st = stems(sample(), TODAY);
  it('sit at offset / 30 of the plot, soonest first', () => {
    expect(st.map((s) => [s.name, s.offset])).toEqual([['Rent', 14], ['Nifty 50 index fund', 18], ['Cloud storage', 25], ['Netflix', 30]]);
    expect(st[0]!.leftPct).toBeCloseTo(46.667, 2);
  });
  it('height is amount over the biggest amount, times 68%', () => {
    expect(st.map((s) => Number(s.heightPct.toFixed(2)))).toEqual([68, 34, 0.44, 2.21]);
  });
  it('the label of the last item grows leftwards', () => {
    expect(st.map((s) => s.align)).toEqual(['center', 'center', 'center', 'end']);
    expect(stems([rule({ name: 'Today', amountMinor: 100, schedule: { kind: 'weekly', weekday: 0 }, nextDue: TODAY })], TODAY)[0]!.align).toBe('start');
  });
  it('paused rules vanish', () => {
    const rules = sample();
    rules[0]!.paused = true;
    const next = stems(rules, TODAY);
    expect(next.map((s) => s.name)).not.toContain('Rent');
    expect(next[0]!.heightPct).toBeCloseTo(68, 5); // Nifty is now the tallest
  });
  it('a weekly rule gives one stem per occurrence with its own key', () => {
    const r = rule({ name: 'Maid', amountMinor: 50_000, schedule: { kind: 'weekly', weekday: 1 }, nextDue: '2026-10-19' });
    const s = stems([r], TODAY);
    expect(s).toHaveLength(5);
    expect(new Set(s.map((x) => x.key)).size).toBe(5);
  });
  it('axis: 31 ticks, five labelled', () => {
    const t = ticks(TODAY);
    expect(t).toHaveLength(31);
    expect(t.filter((x) => x.label).map((x) => x.label)).toEqual(['OCT 18', 'OCT 25', 'NOV 01', 'NOV 08', 'NOV 17']);
    expect(t[30]!.leftPct).toBe(100);
  });
  it('the screen-reader label lists the same payments as the table', () => {
    expect(timelineLabel(st)).toBe('Payments in the next 30 days: Rent ₹20,000 on NOV 01, Nifty 50 index fund ₹10,000 on NOV 05, Cloud storage ₹130 on NOV 12, Netflix ₹649 on NOV 17');
    expect(timelineLabel([])).toBe('No payments leave in the next 30 days');
  });
});

describe('committed each month (spec: 30,779, pausing Rent leaves 10,779)', () => {
  it('sums running rules', () => {
    expect(committedTotal(sample())).toBe(3_077_900);
  });
  it('a paused or ended rule is struck through and left out', () => {
    const rules = sample();
    rules[0]!.paused = true;
    rules[2]!.active = false;
    expect(committedTotal(rules)).toBe(1_064_900);
    expect(committedRows(rules).map((r) => [r.label, r.off])).toEqual([['rent', true], ['+ nifty 50 index fund', false], ['+ cloud storage', true], ['+ netflix', false]]);
  });
  it('isOn, isEnded and the NEXT column', () => {
    const r = rent();
    expect(nextText(r)).toBe('NOV 01');
    expect(nextText({ ...r, paused: true })).toBe('PAUSED');
    expect(nextText({ ...r, active: false })).toBe('ENDED');
    expect(isOn({ ...r, paused: true })).toBe(false);
    expect(isEnded({ ...r, endsOn: '2026-10-31' })).toBe(true);
    expect(isEnded(r)).toBe(false);
  });
});

describe('the list after a change', () => {
  it('a new rule is inserted in due order and the total follows', () => {
    const cur = { items: [rent(), netflix()], committedMinor: 2_064_900 };
    const next = withRule(cur, nifty());
    expect(next.items.map((r) => r.name)).toEqual(['Rent', 'Nifty 50 index fund', 'Netflix']);
    expect(next.committedMinor).toBe(3_064_900);
  });
  it('a changed rule replaces the old one and moves when its due day moved', () => {
    const [r1, r2] = [rent(), nifty()];
    const next = withRule({ items: [r1, r2], committedMinor: 3_000_000 }, { ...r1, nextDue: '2026-11-20', paused: true });
    expect(next.items.map((r) => r.name)).toEqual(['Nifty 50 index fund', 'Rent']);
    expect(next.committedMinor).toBe(1_000_000);
  });
  it('removing drops the row and its amount', () => {
    const rules = sample();
    const next = withoutRule({ items: rules, committedMinor: committedTotal(rules) }, rules[0]!.id);
    expect(next.items).toHaveLength(3);
    expect(next.committedMinor).toBe(1_077_900);
  });
});

describe('skip next', () => {
  it('lands on the due day after the next one', () => {
    expect(dayAfterNext(rent())).toBe('2026-12-01');
    expect(dayAfterNext(rule({ name: 'Maid', amountMinor: 1, schedule: { kind: 'weekly', weekday: 1 }, nextDue: '2026-10-19' }))).toBe('2026-10-26');
  });
  it('a 31st clamps in a short month', () => {
    expect(dayAfterNext(rule({ name: 'Loan', amountMinor: 1, schedule: { kind: 'monthly', day: 31 }, nextDue: '2026-01-31' }))).toBe('2026-02-28');
  });
  it('is null when that was the last payment before the end date', () => {
    expect(dayAfterNext({ ...rent(), endsOn: '2026-11-15' })).toBeNull();
  });
});

describe('the add form', () => {
  const ok = { ...emptyForm(TODAY), name: ' Netflix ', tag: '#Fun', amount: '₹649', day: '17' };
  it('starts on today as a monthly rule', () => {
    expect(emptyForm(TODAY)).toMatchObject({ kind: 'monthly', day: '18', weekday: '1', month: '10', startsOn: '' });
  });
  it('builds the request: normalised tag, paise, empty optionals as null', () => {
    expect(createBody(ok, TODAY)).toEqual({
      ok: true, body: { name: 'Netflix', tag: 'fun', amountMinor: 64_900, schedule: { kind: 'monthly', day: 17 }, note: null, matchHint: null, endsOn: null },
    });
  });
  it('sends startsOn only when given, and the other schedule kinds', () => {
    const w = createBody({ ...ok, kind: 'weekly', weekday: '0', startsOn: '2026-10-20', note: 'to maid', hint: 'maid' }, TODAY);
    expect(w).toEqual({ ok: true, body: { name: 'Netflix', tag: 'fun', amountMinor: 64_900, schedule: { kind: 'weekly', weekday: 0 }, note: 'to maid', matchHint: 'maid', endsOn: null, startsOn: '2026-10-20' } });
    const y = createBody({ ...ok, kind: 'yearly', month: '3', day: '5' }, TODAY);
    expect(y.ok && y.body.schedule).toEqual({ kind: 'yearly', month: 3, day: 5 });
  });
  it('says what is wrong, field by field', () => {
    const r = createBody({ ...ok, name: ' ', tag: '', amount: '0', day: '32' }, TODAY);
    expect(r.ok).toBe(false);
    expect(!r.ok && Object.keys(r.errors).sort()).toEqual(['amount', 'day', 'name', 'tag']);
    const w = createBody({ ...ok, kind: 'weekly', weekday: '' }, TODAY);
    expect(!w.ok && w.errors.weekday).toBeTruthy();
    const y = createBody({ ...ok, kind: 'yearly', month: '13' }, TODAY);
    expect(!y.ok && y.errors.month).toBeTruthy();
  });
  it('refuses a first payment in the past and an end before the start', () => {
    const past = createBody({ ...ok, startsOn: '2026-10-17' }, TODAY);
    expect(!past.ok && past.errors.startsOn).toBeTruthy();
    const end = createBody({ ...ok, startsOn: '2026-11-01', endsOn: '2026-10-25' }, TODAY);
    expect(!end.ok && end.errors.endsOn).toBeTruthy();
  });
  it('turns the server\'s field names into form fields', () => {
    expect(formErrorsFrom({ amountMinor: 'x', matchHint: 'y', categoryId: 'z', unknown: 'q' })).toEqual({ amount: 'x', hint: 'y', tag: 'z' });
  });
});

describe('the change form', () => {
  it('opens with the rule filled in and gives the same rule back', () => {
    const r = rule({ name: 'Cloud storage', amountMinor: 13_050, schedule: { kind: 'yearly', month: 3, day: 5 }, nextDue: '2027-03-05', note: 'subscription', matchHint: 'icloud', endsOn: '2030-03-05' });
    const f = formFrom(r);
    expect(f).toMatchObject({ name: 'Cloud storage', tag: 'cloud storage', amount: '130.5', kind: 'yearly', month: '3', day: '5', note: 'subscription', hint: 'icloud', endsOn: '2030-03-05' });
    expect(patchBody(f)).toEqual({
      ok: true, body: { name: 'Cloud storage', tag: 'cloud storage', amountMinor: 13_050, schedule: { kind: 'yearly', month: 3, day: 5 }, note: 'subscription', matchHint: 'icloud', endsOn: '2030-03-05' },
    });
  });
  it('a weekly rule keeps its weekday, and clearing optional fields sends null', () => {
    const f = formFrom(rule({ name: 'Maid', amountMinor: 50_000, schedule: { kind: 'weekly', weekday: 6 }, nextDue: '2026-10-24' }));
    expect(f.weekday).toBe('6');
    expect(patchBody({ ...f, note: '  ', hint: '' })).toMatchObject({ ok: true, body: { schedule: { kind: 'weekly', weekday: 6 }, note: null, matchHint: null, endsOn: null } });
  });
  it('validates like the add form', () => {
    const r = patchBody({ ...formFrom(rent()), amount: 'abc' });
    expect(!r.ok && r.errors.amount).toBe('Enter an amount like ₹649.');
  });
});

describe('nextRule', () => {
  it('is the running rule due first', () => {
    expect(nextRule(sample())?.name).toBe('Rent');
    expect(nextRule([rent(), { ...nifty(), nextDue: '2026-10-25' }])?.name).toBe('Nifty 50 index fund');
  });
  it('skips paused and ended rules; null when none runs', () => {
    expect(nextRule([{ ...rent(), paused: true }, netflix()])?.name).toBe('Netflix');
    expect(nextRule([{ ...rent(), paused: true }, { ...netflix(), active: false }])).toBeNull();
    expect(nextRule([])).toBeNull();
  });
});
