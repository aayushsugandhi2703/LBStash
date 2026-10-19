import { css3, dayScale, formatInr, inr, inSentence, joinPlain, monthDay, monthName, nextMonthName, type Paise, pct, shortMonth, wholeRupees } from '@/common';
import type { AttentionItem, BalanceCheckDto, DashboardRes, ReportDailyRes } from '@/contracts';

/** Now page view-model (docs/ui-spec/01-now): flow diagram, day bars, hero copy, action links, balance-check wording. */

const FLOW_H = 330;
const FLOW_GAP = 22;
/** The diagram has room for seven destinations: six spending groups and "Still available". */
const FLOW_MAX_SPENT = 6;

interface FlowRow { name: string; v: Paise; av: boolean }

/** Right-hand rows: spent groups biggest first, extras beyond the sixth folded into "Other", then "Still available". */
export function flowRows(flow: DashboardRes['flow'], maxSpent = FLOW_MAX_SPENT): FlowRow[] {
  const spent = flow.slice(0, -1).filter((f) => f.amount > 0);
  const available = flow.length > 0 ? (flow[flow.length - 1]?.amount ?? 0) : 0;
  const rows: FlowRow[] = spent.slice(0, spent.length > maxSpent ? maxSpent - 1 : maxSpent).map((f) => ({ name: f.name, v: f.amount, av: false }));
  if (spent.length > maxSpent) rows.push({ name: 'Other', v: spent.slice(maxSpent - 1).reduce((t, f) => t + f.amount, 0), av: false });
  if (available > 0) rows.push({ name: 'Still available', v: available, av: true });
  return rows;
}

interface FlowGeometry {
  total: Paise;
  ribbons: { d: string; title: string; av: boolean }[];
  /** Right nodes and labels, in % of the 330-unit plot. `heightPct` gets a 2px floor in CSS. */
  nodes: { name: string; amount: string; av: boolean; topPct: number; heightPct: number; labelTopPct: number }[];
}

/** The spec's exact geometry: left side without gaps, right side with a 22-unit gap between nodes. */
export function flowGeometry(rows: FlowRow[], H = FLOW_H, GAP = FLOW_GAP): FlowGeometry {
  const total = rows.reduce((t, r) => t + r.v, 0);
  if (total <= 0) return { total: 0, ribbons: [], nodes: [] };
  const S = H - GAP * (rows.length - 1);
  const f = (n: number) => n.toFixed(2);
  const ribbons: FlowGeometry['ribbons'] = [];
  const nodes: FlowGeometry['nodes'] = [];
  let ly = 0;
  let ry = 0;
  for (const r of rows) {
    const lh = (r.v / total) * H;
    const rh = (r.v / total) * S;
    const ly1 = ly + lh;
    const ry1 = ry + rh;
    ribbons.push({ d: `M0 ${f(ly)} C50 ${f(ly)} 50 ${f(ry)} 100 ${f(ry)} L100 ${f(ry1)} C50 ${f(ry1)} 50 ${f(ly1)} 0 ${f(ly1)} Z`, title: `${r.name} · ${inr(r.v)}`, av: r.av });
    nodes.push({ name: r.name, amount: formatInr(r.v), av: r.av, topPct: css3((ry / H) * 100), heightPct: css3((rh / H) * 100), labelTopPct: css3(((ry + rh / 2) / H) * 100) });
    ly = ly1;
    ry = ry1 + GAP;
  }
  return { total, ribbons, nodes };
}

/** Left stack: carried over over income, each as a flex weight and a label centred on its segment. */
export function leftStack(carried: Paise, income: Paise): { name: string; amount: string; flex: number; centrePct: number; kind: 'carried' | 'income' }[] {
  const sum = carried + income;
  if (sum <= 0) return [];
  const parts = [{ name: 'Carried over', v: carried, kind: 'carried' as const }, { name: 'Income', v: income, kind: 'income' as const }].filter((p) => p.v > 0);
  let at = 0;
  return parts.map((p) => {
    const centre = at + (p.v / sum) * 50;
    at += (p.v / sum) * 100;
    return { name: p.name, amount: formatInr(p.v), flex: p.v, centrePct: css3(centre), kind: p.kind };
  });
}

export const flowLabel = (total: Paise, available: Paise): string =>
  `Flow of ${inr(total)} from carried-over money and income into spending categories and the ${inr(Math.max(0, available))} still available`;

interface DayChart {
  scale: { max: Paise; mid: Paise };
  /** Top of the average line in % of the plot (null when there is no average yet). */
  avgTopPct: number | null;
  days: { day: number; future: boolean; heightPct: number; axis: string | null; tip: string; tipSide: 'centre' | 'end' }[];
  legend: string;
}

/** Axis labels under days 1, 5, 10, 15, 20, 25 and the last, plus today; a label right next to today yields to it. */
export function axisDays(daysInMonth: number, today: number): Set<number> {
  const base = [1, 5, 10, 15, 20, 25, daysInMonth].filter((d) => d <= daysInMonth && (today <= 0 || Math.abs(d - today) >= 2 || d === today));
  const out = new Set(base);
  if (today >= 1 && today <= daysInMonth) out.add(today);
  return out;
}

export function dayChart(r: ReportDailyRes): DayChart {
  const max = Math.max(0, r.averageMinor, ...r.items.map((i) => i.spentMinor));
  const scale = dayScale(max);
  const n = r.items.length;
  const labels = axisDays(n, r.dayOfMonth);
  const mon = shortMonth(r.month);
  const days = r.items.map((it, i) => {
    const day = i + 1;
    const future = day > r.dayOfMonth;
    return {
      day, future,
      heightPct: future ? 0 : css3(pct(it.spentMinor, scale.max)),
      axis: labels.has(day) ? String(day) : null,
      tip: `${mon} ${day} · ${inr(it.spentMinor)}`,
      tipSide: n - day < 2 ? ('end' as const) : ('centre' as const),
    };
  });
  const left = r.fixedCategories.length ? ` · ${joinPlain(r.fixedCategories.map(inSentence))} left out` : '';
  const hasAvg = r.dayOfMonth > 0 && r.totalMinor > 0;
  return {
    scale,
    avgTopPct: hasAvg ? css3(100 - pct(r.averageMinor, scale.max)) : null,
    days,
    legend: hasAvg ? `average ${inr(wholeRupees(r.averageMinor))} a day${left}` : `nothing spent yet${left}`,
  };
}

/** The sentence under the hero number, in three parts so the middle can carry the accent underline. */
export function heroSentence(d: DashboardRes): { before: string; em?: string; after?: string } {
  const month = monthName(d.month);
  if (d.balance.available < 0) return { before: `You have spent more than you had. Add money, or hold back, before ${month} ends.` };
  if (d.safeToSpend.daysLeft === 0) return { before: `is what ${month} left you, and it carries into ${nextMonthName(d.month)}.` };
  if (d.safeToSpend.perDay <= 0) return { before: `is yours to spend. The plan has nothing left for the rest of ${month}.` };
  return {
    before: 'is yours to spend. At ',
    em: `${inr(d.safeToSpend.perDay)} a day`,
    after: ` you finish ${month} on plan, and the rest carries into ${nextMonthName(d.month)}.`,
  };
}

interface NowLink { key: string; tag: string; text: string; href: string; marker?: 'warn' | 'danger' }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The strip under the hero: WATCH, TAG, LOOK, NEXT (and a line for balance-check gaps), from `attention` in the API's order. */
export function nowLinks(attention: AttentionItem[]): NowLink[] {
  const out: NowLink[] = [];
  const limits = attention.filter((a): a is Extract<AttentionItem, { kind: 'limit' }> => a.kind === 'limit');
  const worst = limits[0];
  if (worst) {
    const more = limits.length > 1 ? `, and ${limits.length - 1} more` : '';
    out.push({
      key: 'limit', tag: 'WATCH', href: '/limits', marker: worst.status === 'over' ? 'danger' : 'warn',
      text: worst.status === 'over' ? `${worst.category} is over its limit${more}` : `${worst.category} is at ${worst.pct}% of its limit${more}`,
    });
  }
  for (const a of attention) {
    if (a.kind === 'untagged') out.push({ key: 'untagged', tag: 'TAG', href: '/ledger?cat=needs-tag', text: `${plural(a.count, 'payment needs', 'payments need')} a tag` });
    else if (a.kind === 'needs_look') out.push({ key: 'look', tag: 'LOOK', href: '/ledger/unread', text: `${plural(a.count, 'message', 'messages')} could not be read` });
    else if (a.kind === 'unaccounted') out.push({ key: 'unaccounted', tag: 'GAP', href: '/ledger?src=unaccounted', text: `${plural(a.count, 'gap', 'gaps')} from a balance check still to tag` });
    else if (a.kind === 'recurring') out.push({ key: 'next', tag: 'NEXT', href: '/repeats', text: `${a.name} ${inr(a.amount)} on ${nextDue(a.due)}` });
  }
  return out;
}

/** "Nov 1" from 2026-11-01 (a day key has no zone: format it in UTC). */
export function nextDue(due: string): string {
  const [m, d] = monthDay(`${due}T12:00:00Z`, 'UTC').split(' ') as [string, string];
  return `${m.charAt(0)}${m.slice(1).toLowerCase()} ${d}`;
}

const DEGRADED: Record<string, string> = { budgets: 'limits', alerts: 'alerts', recurring: 'the next payment', ingest: 'unread messages' };
/** "Could not read limits and the next payment just now." or null. */
export function degradedNote(parts: string[]): string | null {
  if (parts.length === 0) return null;
  return `Could not read ${joinPlain(parts.map((p) => DEGRADED[p] ?? p))} just now.`;
}

/** "6 hours", "1 hour", "45 minutes": how long a gap waits before it is booked. */
export function graceText(ms: number): string {
  const hours = ms / 3_600_000;
  if (hours >= 1) { const h = Math.round(hours); return `${h} ${h === 1 ? 'hour' : 'hours'}`; }
  const m = Math.max(1, Math.round(ms / 60_000));
  return `${m} ${m === 1 ? 'minute' : 'minutes'}`;
}

/** The yellow "gap" sentence (spec 02): bank lower = money left unexplained, bank higher = money arrived unexplained. */
export function gapSentence(check: Pick<BalanceCheckDto, 'gapMinor' | 'checkedAt' | 'graceEndsAt'>): string {
  const amount = inr(Math.abs(check.gapMinor));
  const lead = check.gapMinor < 0 ? `${amount} left your account and no message explains it.` : `${amount} more is in your account than the ledger says, and no message explains it.`;
  const wait = check.graceEndsAt ? graceText(new Date(check.graceEndsAt).getTime() - new Date(check.checkedAt).getTime()) : null;
  return `${lead} It is booked as an Unaccounted entry${wait ? ` after ${wait}` : ' soon'}, unless the missing message arrives first.`;
}
