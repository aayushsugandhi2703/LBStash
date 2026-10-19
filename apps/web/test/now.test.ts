import { describe, expect, it } from 'vitest';
import type { DashboardRes, ReportDailyRes } from '@/contracts';
import { axisDays, dayChart, degradedNote, flowGeometry, flowLabel, flowRows, gapSentence, graceText, heroSentence, leftStack, nextDue, nowLinks } from '@/features/now';

const R = (n: number) => n * 100;

// ui-spec §6: carried 27,300 + income 50,000 − spent 39,709 = 37,591; plan left 5,791 ÷ 13 = 445
const flow: DashboardRes['flow'] = [
  { name: 'Rent', amount: R(20000) }, { name: 'SIP', amount: R(10000) }, { name: 'Food', amount: R(5420) },
  { name: 'Fun', amount: R(1640) }, { name: 'Travel', amount: R(1350) }, { name: 'Bills', amount: R(1299) },
  { name: 'Still available', amount: R(37591) },
];
const dash = (over: Partial<DashboardRes> = {}): DashboardRes => ({
  month: '2026-10', dayOfMonth: 18, daysInMonth: 31,
  balance: { carriedOver: R(27300), income: R(50000), spent: R(39709), available: R(37591) },
  safeToSpend: { planLeft: R(5791), daysLeft: 13, perDay: R(445) },
  flow, attention: [], lastCapturedAt: null, untaggedCount: 1, unaccountedCount: 0, needsLookCount: 2, alertBadgeCount: 0, degraded: [],
  ...over,
});

describe('flow rows and geometry', () => {
  it('keeps the seven sample destinations in order', () => {
    const rows = flowRows(flow);
    expect(rows.map((r) => r.name)).toEqual(['Rent', 'SIP', 'Food', 'Fun', 'Travel', 'Bills', 'Still available']);
    expect(rows.at(-1)?.av).toBe(true);
    expect(rows.reduce((t, r) => t + r.v, 0)).toBe(R(77300));
  });

  it('matches the design formula (H 330, gap 22, S 198)', () => {
    const rows = flowRows(flow);
    const g = flowGeometry(rows);
    expect(g.total).toBe(R(77300));
    const H = 330, GAP = 22, S = H - GAP * 6;
    let ry = 0;
    rows.forEach((r, i) => {
      const rh = (r.v / R(77300)) * S;
      expect(g.nodes[i]!.topPct).toBeCloseTo((ry / H) * 100, 3);
      expect(g.nodes[i]!.heightPct).toBeCloseTo((rh / H) * 100, 3);
      expect(g.nodes[i]!.labelTopPct).toBeCloseTo(((ry + rh / 2) / H) * 100, 3);
      ry += rh + GAP;
    });
    // the last node ends on the bottom edge of the plot
    const last = g.nodes.at(-1)!;
    expect(last.topPct + last.heightPct).toBeCloseTo(100, 2);
  });

  it('draws the available ribbon as the largest (about 48.6%) and paths from the left edge', () => {
    const g = flowGeometry(flowRows(flow));
    expect(37591 / 77300).toBeCloseTo(0.4863, 3);
    expect(g.ribbons).toHaveLength(7);
    expect(g.ribbons[0]!.d.startsWith('M0 0.00 C50 0.00 50 0.00 100 0.00 L100 51.23')).toBe(true);
    expect(g.ribbons[0]!.title).toBe('Rent · ₹20,000');
    expect(g.ribbons.filter((r) => r.av)).toHaveLength(1);
    // the three thin ones never touch: 22 units between nodes
    const [fun, travel, bills] = [g.nodes[3]!, g.nodes[4]!, g.nodes[5]!];
    expect((travel.topPct - (fun.topPct + fun.heightPct)) / 100 * 330).toBeCloseTo(22, 1);
    expect((bills.topPct - (travel.topPct + travel.heightPct)) / 100 * 330).toBeCloseTo(22, 1);
    expect(g.nodes[0]!.amount).toBe('20,000');
  });

  it('folds the tail into Other beyond six spending groups, and drops an empty available', () => {
    const many: DashboardRes['flow'] = [
      ...Array.from({ length: 9 }, (_, i) => ({ name: `Cat ${i}`, amount: R(1000 - i * 10) })),
      { name: 'Still available', amount: 0 },
    ];
    const rows = flowRows(many);
    expect(rows).toHaveLength(6);
    expect(rows[5]).toMatchObject({ name: 'Other', av: false });
    expect(rows[5]!.v).toBe(R(950 + 940 + 930 + 920));
    expect(rows.reduce((t, r) => t + r.v, 0)).toBe(many.reduce((t, r) => t + r.amount, 0));
  });

  it('is empty with nothing to show', () => {
    expect(flowRows([{ name: 'Still available', amount: 0 }])).toEqual([]);
    expect(flowRows([])).toEqual([]);
    expect(flowGeometry([]).nodes).toEqual([]);
  });

  it('left stack: labels centred on their segment', () => {
    const [c, i] = leftStack(R(27300), R(50000));
    expect(c).toMatchObject({ name: 'Carried over', amount: '27,300', flex: R(27300), kind: 'carried' });
    expect(c!.centrePct).toBeCloseTo((27300 / 77300) * 50, 2);
    expect(i!.centrePct).toBeCloseTo((27300 / 77300) * 100 + (50000 / 77300) * 50, 2);
    expect(leftStack(0, R(50000))).toHaveLength(1);
    expect(leftStack(0, 0)).toEqual([]);
  });

  it('describes the totals for assistive tech', () => {
    expect(flowLabel(R(77300), R(37591))).toContain('₹77,300');
    expect(flowLabel(R(77300), R(37591))).toContain('₹37,591 still available');
  });
});

const daily = (over: Partial<ReportDailyRes> = {}): ReportDailyRes => {
  const vals = [240, 370, 340, 530, 420, 350, 850, 380, 910, 620, 970, 440, 730, 480, 570, 740, 380, 389];
  const total = vals.reduce((a, b) => a + b, 0);
  return {
    month: '2026-10', dayOfMonth: 18, daysInMonth: 31,
    items: Array.from({ length: 31 }, (_, i) => ({ day: `2026-10-${String(i + 1).padStart(2, '0')}`, spentMinor: R(vals[i] ?? 0) })),
    totalMinor: R(total), averageMinor: Math.round((R(total)) / 18), fixedCategories: ['Rent', 'SIP'], ...over,
  };
};

describe('day by day', () => {
  it('uses the ₹1,000 scale, a 46.1% average line, and the sample bars', () => {
    expect(9709 / 18).toBeCloseTo(539.4, 1);
    const c = dayChart(daily());
    expect(c.scale.max).toBe(R(1000));
    expect(c.scale.mid).toBe(R(500));
    expect(c.avgTopPct).toBeCloseTo(46.1, 0);
    expect(c.days).toHaveLength(31);
    expect(c.days[10]!.heightPct).toBe(97);
    expect(c.days[0]!.heightPct).toBe(24);
    expect(c.days[10]!.tip).toBe('Oct 11 · ₹970');
    expect(c.days.filter((d) => !d.future)).toHaveLength(18);
    expect(c.days.slice(18).every((d) => d.future && d.heightPct === 0)).toBe(true);
    expect(c.legend).toBe('average ₹539 a day · rent and SIP left out');
  });

  it('labels days 1, 5, 10, 15, 18, 20, 25, 31', () => {
    const c = dayChart(daily());
    expect(c.days.filter((d) => d.axis).map((d) => d.day)).toEqual([1, 5, 10, 15, 18, 20, 25, 31]);
    expect([...axisDays(31, 19)].sort((a, b) => a - b)).toEqual([1, 5, 10, 15, 19, 25, 31]);
    expect([...axisDays(30, 30)]).not.toContain(31);
    expect(axisDays(28, 0).has(28)).toBe(true);
  });

  it('grows the scale with big days and anchors the last tooltips to the right edge', () => {
    const c = dayChart(daily({ items: daily().items.map((d, i) => (i === 3 ? { ...d, spentMinor: R(2600) } : d)) }));
    expect(c.scale.max).toBe(R(5000));
    expect(c.days.at(-1)!.tipSide).toBe('end');
    expect(c.days.at(-2)!.tipSide).toBe('end');
    expect(c.days.at(-3)!.tipSide).toBe('centre');
  });

  it('has no average line and says so before anything is spent', () => {
    const c = dayChart(daily({ items: daily().items.map((d) => ({ ...d, spentMinor: 0 })), totalMinor: 0, averageMinor: 0, fixedCategories: [] }));
    expect(c.avgTopPct).toBeNull();
    expect(c.legend).toBe('nothing spent yet');
    expect(c.scale.max).toBe(R(100));
  });
});

describe('hero sentence', () => {
  it('is the design copy at ₹445 a day', () => {
    expect(heroSentence(dash())).toEqual({
      before: 'is yours to spend. At ', em: '₹445 a day', after: ' you finish October on plan, and the rest carries into November.',
    });
  });
  it('changes when the plan has nothing left or the balance is negative', () => {
    expect(heroSentence(dash({ safeToSpend: { planLeft: R(-100), daysLeft: 13, perDay: 0 } })).em).toBeUndefined();
    expect(heroSentence(dash({ safeToSpend: { planLeft: R(-100), daysLeft: 13, perDay: 0 } })).before).toContain('nothing left for the rest of October');
    const neg = heroSentence(dash({ balance: { carriedOver: 0, income: 0, spent: R(100), available: R(-100) } }));
    expect(neg.before).toContain('spent more than you had');
  });
});

describe('action links', () => {
  it('maps attention items to WATCH, TAG, LOOK, NEXT in order', () => {
    const links = nowLinks([
      { kind: 'limit', category: 'Fun', pct: 82, status: 'close' },
      { kind: 'untagged', count: 1 },
      { kind: 'needs_look', count: 2 },
      { kind: 'recurring', name: 'Rent', amount: R(20000), due: '2026-11-01' },
    ]);
    expect(links.map((l) => [l.tag, l.text, l.href])).toEqual([
      ['WATCH', 'Fun is at 82% of its limit', '/limits'],
      ['TAG', '1 payment needs a tag', '/ledger?cat=needs-tag'],
      ['LOOK', '2 messages could not be read', '/ledger/unread'],
      ['NEXT', 'Rent ₹20,000 on Nov 1', '/repeats'],
    ]);
    expect(links[0]!.marker).toBe('warn');
  });
  it('speaks plurals, over-limit and extra limits', () => {
    const links = nowLinks([
      { kind: 'limit', category: 'Food', pct: 112, status: 'over' },
      { kind: 'limit', category: 'Fun', pct: 90, status: 'close' },
      { kind: 'untagged', count: 3 },
      { kind: 'needs_look', count: 1 },
      { kind: 'unaccounted', count: 2 },
    ]);
    expect(links[0]).toMatchObject({ text: 'Food is over its limit, and 1 more', marker: 'danger' });
    expect(links[1]!.text).toBe('3 payments need a tag');
    expect(links[2]!.text).toBe('1 message could not be read');
    expect(links[3]).toMatchObject({ tag: 'GAP', text: '2 gaps from a balance check still to tag' });
  });
  it('formats due dates without a zone shift', () => {
    expect(nextDue('2026-11-01')).toBe('Nov 1');
    expect(nextDue('2026-12-25')).toBe('Dec 25');
  });
  it('names the parts that could not be read', () => {
    expect(degradedNote([])).toBeNull();
    expect(degradedNote(['budgets', 'recurring'])).toBe('Could not read limits and the next payment just now. Those figures are missing.');
  });
});

describe('balance check wording', () => {
  it('says how long a gap waits', () => {
    expect(graceText(6 * 3_600_000)).toBe('6 hours');
    expect(graceText(3_600_000)).toBe('1 hour');
    expect(graceText(45 * 60_000)).toBe('45 minutes');
  });
  it('explains a gap in both directions with the grace period', () => {
    const base = { checkedAt: '2026-10-18T10:00:00.000Z', graceEndsAt: '2026-10-18T16:00:00.000Z' };
    expect(gapSentence({ ...base, gapMinor: R(-180) })).toBe(
      '₹180 left your account and no message explains it. It is booked as an Unaccounted entry after 6 hours, unless the missing message arrives first.');
    expect(gapSentence({ ...base, gapMinor: R(500) })).toContain('₹500 more is in your account than the ledger says');
    expect(gapSentence({ ...base, graceEndsAt: null, gapMinor: R(-180) })).toContain('booked as an Unaccounted entry soon');
  });
});
