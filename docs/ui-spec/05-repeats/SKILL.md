---
name: budget-ui-repeats
description: Build the "05 Repeats" recurring-payments page of the Ledger budget tracker: committed-per-month arithmetic, a 30-day lollipop timeline of upcoming payments, a rules table with pause switches that recompute totals. Matches reference/Recurring.dc.html.
---

# 05 · Repeats

Reference: `reference/Recurring.dc.html` · Route `/repeats` · Requires `00-design-system`.

**Purpose.** List the payments that leave the account automatically, show when the next ones land, and let the user pause any of them.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `Repeats` icon / `Repeats` |
| Description (`.opt`) | "Payments that leave your account on their own. They post on the due date." |
| Block header | mono caps 11px muted `COMMITTED EACH MONTH`, `margin-top:24px`, `padding-bottom:7px`, `border-bottom:1px solid ink` |
| Ledger-math | rows: `rent 20,000`, `+ nifty 50 index fund 10,000`, `+ cloud storage 130`, `+ netflix 649`, final `= committed 30,779` (**ink**: committed payments are money out). Row labels are the lower-cased rule names, first without a `+`. **Paused rules** show label and value in `#CFCFD6` with `line-through`, and the total excludes them |
| Note (`.opt2`) | 13px muted with top rule: "If your phone already caught one of these within 2 days of its due date, it is linked to the rule, never counted twice." |

### Main (flex column)
1. **Heading row**: `h2` "The next 30 days" (18px/500) and mono 11px muted "stem height = amount · oct 18 to nov 17".
2. **Timeline** (`border-top:1px solid ink; flex:1 1 220px; min-height:140px; overflow-x:auto`, inner `min-width:620px`):
   - Plot: `position:relative; flex:1; min-height:110px; margin:0 8px; border-bottom:1px solid ink`.
   - **Stems** for each *active* rule, positioned at `left = offsetDays / 30 * 100%` where today = day 0 (Oct 18):

     | Rule | Offset | Stem height |
     |---|---|---|
     | Rent (Nov 1) | 14 | `max(5px, 20000/20000 × 68%)` = 68% |
     | Nifty 50 index fund (Nov 5) | 18 | 34% |
     | Cloud storage (Nov 12) | 25 | `max(5px, 0.65%)` → 5px |
     | Netflix (Nov 17) | 30 | `max(5px, 2.2%)` → 5px |

     Height formula `max(5px, amount/20000 × 68%)`. The stem is 3px wide, ink, grows with `scaleY` from bottom (stagger 100ms); a **11×11 ink square cap** sits on top (`bottom: calc(max(5px, h%) − 5px)`); a label (name 14px/500 above amount mono 11px muted) sits `calc(max(5px, h%) + 14px)` above the baseline, centred on the stem. The **last** item (offset 30) right-aligns its label (`right:-8px; text-align:right`) so it stays inside.
   - **Axis ticks** below the plot (height 40px): 31 ticks (days 0..30) at `left = d/30*100%`, 1px ink, height 5px (10px at labelled days). Labels (mono 11px muted, `top:16px`) at offsets 0, 7, 14, 21, 30: `OCT 18`, `OCT 25`, `NOV 01`, `NOV 08`, `NOV 17`; the first is left-aligned, the last right-aligned (`translateX(-100%)`), others centred.
3. **Rules table** (`margin-top:12px`, block `min-width:700px`, horizontal scroll):
   - Header: mono 11px caps muted, `border-top:1px solid ink`, bottom rule `#E6E6EA`, gap 20px, padding 10px 0. Columns: `PAYMENT` flex · `TAG` 70px · `AMOUNT` 100px right · `REPEATS` 120px · `NEXT` 80px · `ON` 60px right.
   - Row: `padding: var(--row-pad) 0; border-bottom:1px solid #E6E6EA`; hover `--hover-row`.

     | Cell | Spec |
     |---|---|
     | Payment | name 16px/500 (muted when paused) + note 13px muted below |
     | Tag | mono 13px `#rent` |
     | Amount | mono 14px/500 `₹20,000` |
     | Repeats | mono 13px `#3B3B42` e.g. `monthly · 1st` |
     | Next | mono 13px e.g. `NOV 01`; shows `PAUSED` when off |
     | On | switch 36×20 |

4. **Primary button** `+ New repeating payment` (36px, ink, `padding-top:14px` wrapper).

## Data

| Id | Name | Note | Tag | Amount | Repeats | Next | Offset |
|---|---|---|---|---|---|---|---|
| 1 | Rent | to landlord | rent | 20,000 | monthly · 1st | NOV 01 | 14 |
| 2 | Nifty 50 index fund | sip | sip | 10,000 | monthly · 5th | NOV 05 | 18 |
| 4 | Cloud storage | subscription | bills | 130 | monthly · 12th | NOV 12 | 25 |
| 3 | Netflix | subscription | fun | 649 | monthly · 17th | NOV 17 | 30 |

Table order: Rent, Nifty 50, Cloud storage, Netflix (by due date).

## State

`off: Record<id, boolean>` (default `{}`). Toggling a switch flips `off[id]`.

```ts
active    = rules.filter(r => !off[r.id])
committed = sum(active.amount)          // 30,779 when all on
stems     = active.map(...)             // paused rules vanish from the timeline
```
- Paused row: name `#6B6B73`, `Next` reads `PAUSED`, switch off colour, aside arithmetic line struck through.
- The aria-label of each switch is `Pause {name}` / `Resume {name}`.

## Behaviour notes

- Rules post themselves on the due date (a scheduled job server-side); this page only displays and pauses them.
- If a captured phone debit of the same amount appears within ±2 days of the due date and matches the rule's payee, link it to the rule instead of double counting.

## Acceptance checklist

- [ ] Initial total 30,779; pausing Rent → 10,779, Rent's stem and arithmetic line disappear/strike through.
- [ ] Rent stem is the tallest (68% of the plot); Cloud storage and Netflix are 5px stubs with ink squares on top.
- [ ] Netflix label right-aligns and never leaves the plot.
- [ ] Ticks: 31 in total, five labelled (`OCT 18`, `OCT 25`, `NOV 01`, `NOV 08`, `NOV 17`).
- [ ] Timeline grows on taller windows (flex) and keeps ≥110px plot on short ones.
