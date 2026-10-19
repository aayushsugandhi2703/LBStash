---
name: budget-ui-trends
description: Build the "Trends" page of the Ledger budget tracker: one sentence, one chart (money in and out for six months, with this month's pace) and a short plain list of what is changing. No toggles. Matches reference/Reports.dc.html.
---

# 06 · Trends

Reference: `reference/Reports.dc.html` · Route `/trends` · Requires `00-design-system`.

**Purpose.** Answer two questions in a glance: how much do I keep in a month, and is this month different? Nothing else on the page.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `Trends` icon / `Trends` |
| Description (`.opt`) | "How your money has moved over the last six months." |
| Three stat blocks | wrapper `margin-top:24px; border-top:1px solid ink`; each `padding: clamp(6px,1.4vh,13px) 0; border-bottom:1px solid #E6E6EA`: mono caps 11px muted label, figure `--fs-fig-lg` weight 300 tracking −0.04em, mono 11px muted note |

| Label | Figure | Note |
|---|---|---|
| `AVG MONTHLY SPEND` | `₹44,460` | may to sep, full months |
| `AVG KEPT` (green) | `11.8%` | of income, same months |
| `BALANCE SINCE MAY` (green) | `+₹31,191` | 6,400 to 37,591 |

### Main (top to bottom, no toggles)
1. **Headline** (`.opt`, `--fs-lead`, `#3B3B42`, max 900px): "You keep about ₹5,940 a month. October is heading for ₹3,280, a tighter month than usual." ("a better month than usual" when the pace is above the average.)
2. **Chart section** (`flex:1; border-top:1px solid ink; padding-top:14px`): `h2` "Money in and out" (18px/500) on the left, legend on the right: `■ money in` (accent), `■ money out` (ink), `▨ where October ends at this pace` (ink hatch). Plot `margin:24px 0 52px 40px; flex:1; min-height:130px`.
3. **List** (`.opt2`, hidden on short screens): mono caps 11px muted header "OCTOBER AGAINST A USUAL MONTH" with an ink rule, then four rows.

## The chart

Scale 0–60K, solid 1px `#E6E6EA` gridlines at 60K, 40K, 20K and a 1px ink baseline; axis labels mono 11px muted at `left:-40px; top:-8px`. Six month columns (`<button class="grp">`, `flex:1`, no gap), each holding two thin bars side by side (`width:30%; max-width:30px`, 3px apart): **money in** and **money out**, heights `value/60000`. **Both bars shade from a deeper tone at the base to the normal tone at the tip, kept narrow so they read as solid colour with depth:** money in `linear-gradient(0deg, #005C3D, #00A06B)`, money out `linear-gradient(0deg, #0E0E10, #4A4A52)`. The legend swatches use the same gradients. The hatched pace block stays a flat ink hatch. Under each month name a second line shows what was kept in green mono 500 (`+8.8K`, `+5.2K`, `+4.7K`, `+6.9K`, `+4.1K`, and for October `+3.3K pace`); a muted `kept` label sits at the left of that line.

**October** shows its money-out bar solid up to 39,709, then a hatched block (`repeating-linear-gradient(135deg, ink 0 1.5px, transparent 1.5px 6px)`) up to the pace total 46,720, with a 2px gap between them. Pace is the Limits rule: flexible spend so far ÷ 18 × 31, rounded to ₹10, plus the fixed Rent and SIP (30,000).

**Hover or keyboard focus** on a column shows a pale band and a tooltip beside the column (right of it for the left half, left of it for the right half; ink, mono 11px): month · `in ₹50,000` · `out ₹41,200` · `kept ₹8,800 · 17.6%`. October reads `out ₹39,709 so far` and `heading for ₹3,280 kept`.

## The list

Rows `padding: var(--row-pad) 0; border-bottom:1px solid #E6E6EA`, sorted from most above usual to most below. Columns: category (`--fs-title`, 500, 80px) · `usually ₹7,590` (mono 13px muted) · `heading for ₹9,330` (mono 13px) · change (mono 13px 500, right-aligned, `▲ ₹1,740 more` or `▼ ₹610 less`).

| Category | Usually (full months) | October pace | Change |
|---|---|---|---|
| Food | 7,590 | 9,330 | ▲ ₹1,740 more |
| Fun | 1,430 | 2,820 | ▲ ₹1,390 more |
| Bills | 2,500 | 2,240 | ▼ ₹260 less |
| Travel | 2,940 | 2,330 | ▼ ₹610 less |

Rent and SIP are left out because they never change.

## Data

| Month | In | Out | Kept | Month-end balance |
|---|---|---|---|---|
| May | 50,000 | 41,200 | 8,800 | 6,400 |
| Jun | 50,000 | 44,800 | 5,200 | 11,600 |
| Jul | 52,000 | 47,300 | 4,700 | 16,300 |
| Aug | 50,000 | 43,100 | 6,900 | 23,200 |
| Sep | 50,000 | 45,900 | 4,100 | 27,300 |
| Oct (day 18) | 50,000 | 39,709 so far, 46,720 at pace | 3,280 at pace | 37,591 today |

## Notes

- Colour has one job: green = money in or kept, ink = money out (each as a narrow dark-to-lighter shade); hatching means "not final yet" and works without colour. The product is light-only, so there is no dark variant.
- Plot geometry is in %, so the chart stretches with the window. On short screens the headline and the list hide first.
- A per-category table and a range switch were tried and removed to keep the page simple. They can come back later as a "More detail" link.

## Acceptance checklist

- [ ] One chart, one sentence, one short list; no toggles; no page scroll.
- [ ] Six month columns with in and out bars; kept amount under every month name.
- [ ] October: solid 39.7K plus a hatched block ending at 46.7K; label `+3.3K pace`.
- [ ] Hover or Tab shows the tooltip for every month.
- [ ] The list shows Food, Fun, Bills, Travel in that order with the figures above.
