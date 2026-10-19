---
name: budget-ui-now
description: Build the "01 Now" overview page of the Ledger budget tracker: hero available-balance number, plain-language sentence, three action links, and a toggled panel with a money-flow (Sankey-style) diagram and a day-by-day spending bar chart. Matches reference/Main.dc.html.
---

# 01 · Now

Reference: `reference/Main.dc.html` · Route `/` · Requires `00-design-system`.

**Purpose.** One glance answers: how much do I have, how much can I spend today, where did the month's money go.

## Layout

Shell from the design system, `active = Now`. Main column is a flex column: hero → links row → panel (`flex:1`).

### Aside
| Element | Spec |
|---|---|
| Glyph | `Now` icon (see design system) |
| `h1` | `Now` |
| Description (`.opt`) | "Where you stand today, and where October's money went." |
| Ledger-math A (`margin-top:28px`) | `carried over` **27,300** (green) / `+ income` **50,000** (green) / `− spent` 39,709 (ink, money out) / **`= available 37,591`** (ink, it is a balance) |
| Ledger-math B (`.opt2`, `margin-top:24px`) | `plan left 5,791` / `÷ days left 13` / **`= per day 445`** (accent) |

### Main: hero (`rise` animation)
1. Mono label `AVAILABLE TO YOU` (11px, +0.06em, muted).
2. Number (colour **ink**, because it is your balance, not a movement of money): `₹` (`.38em`, muted, `vertical-align:.95em`, `margin-right:6px`) + `37,591`; `var(--fs-display)` = `clamp(52px, min(8.6vw, 13vh), 150px)`, weight 300, tracking −0.065em, `line-height 1`, `margin-top 6px`.
3. Sentence (`margin-top:12px`, `var(--fs-lead)` = `clamp(17px, 1.4vw, 22px)`, `#3B3B42`, `max-width 900px`, `line-height 1.45`, tracking −0.01em):
   "is yours to spend. At **₹445 a day** you finish October on plan, and the rest carries into November."
   `₹445 a day` is ink with a 2px accent underline, `text-underline-offset 4px`.

### Main: action links row
`margin-top:20px; border-top:1px solid #E6E6EA; display:flex; flex-wrap:wrap; gap:0 32px`. Four links, each `min-height:44px; padding:12px 0; gap:10px`, hover colour accent, trailing `→`:

| Tag (mono 11px caps muted) | Marker | Text | Goes to |
|---|---|---|---|
| `WATCH` | 7px `--warn` square | Fun is at 82% of its limit | Limits |
| `TAG` | none | 1 payment needs a tag | Ledger |
| `NEXT` | none | Rent ₹20,000 on Nov 1 | Repeats |

### Main: panel
`margin-top:20px; border-top:1px solid ink; padding-top:14px; flex:1; display:flex; flex-direction:column; min-height:0`.

Header row: `h2` (18px/500) whose text is **"Where it went"** in Flow view and **"Day by day"** in Day view, and a segmented control **[Flow] [Day by day]** (32px high). State `view: 'flow' | 'days'`, default `flow`.

## Flow view

A horizontal flow diagram: one source stack on the left splits into seven destinations on the right.

Container: `margin-top:14px; flex:1; min-height:220px; overflow-x:auto`, inner row `min-width:640px; width:100%; display:flex`. Fade-in 1s. Columns left to right:

| Column | Width | Content |
|---|---|---|
| Left labels | `clamp(110px, 10vw, 160px)` | two right-aligned labels (`right:16px`), vertically centred (`top: %` + `translateY(-50%)`) on their segment |
| Left node | 12px | stacked `flex: 27300 1 0` (colour `#9A9AA6`) over `flex: 50000 1 0` (ink, `border-top:2px solid #fff`) |
| Ribbons | `flex:1` | `<svg viewBox="0 0 100 330" preserveAspectRatio="none">` absolutely filling its box |
| Right nodes | 12px | seven rectangles, `top` and `height` in % of 330 |
| Right labels | `clamp(180px, 16vw, 260px)` | seven rows, `top: calc(Y% − 10px)`, height 20, `left:18px`, name left and amount right |

Left labels: **Carried over** `27,300` and **Income** `50,000` (name 14px/500; amount mono 11px, **green** because both are money in).

### Geometry (exact)

```ts
const H = 330, GAP = 22;
const cats = [
  { name:'Rent', v:20000 }, { name:'SIP', v:10000 }, { name:'Food', v:5420 },
  { name:'Fun',  v:1640  }, { name:'Travel', v:1350 }, { name:'Bills', v:1299 },
  { name:'Still available', v:37591, av:true },
];
const total = 77300;                    // sum of v
const S = H - GAP * (cats.length - 1);  // 198, drawable height on the right
let ly = 0, ry = 0;
for (const c of cats) {
  const lh = c.v / total * H;           // left height (no gaps)
  const rh = c.v / total * S;           // right height
  const ly1 = ly + lh, ry1 = ry + rh;
  // ribbon path in viewBox units (x 0..100, y 0..330)
  const d = `M0 ${ly} C50 ${ly} 50 ${ry} 100 ${ry} L100 ${ry1} C50 ${ry1} 50 ${ly1} 0 ${ly1} Z`;
  // right node: top = ry/H*100 %, height = max(2px, rh/H*100 %)
  // right label: top = calc((ry + rh/2)/H*100 % - 10px)
  ly = ly1;  ry = ry1 + GAP;
}
```

| Item | Style |
|---|---|
| Spent ribbon | fill `#EDEDF1`, hover `#C9CDDB`, `transition fill .15s` |
| "Still available" ribbon | fill `#D8F3E7`, hover `#B3E6CD` |
| Spent right node | ink |
| Available right node | `--accent` |
| Label name | 14px/500; "Still available": 14px/600 accent |
| Label amount | mono 11px muted, `en-IN` grouping, no ₹ |

Each ribbon has an SVG `<title>` ("Rent · ₹20,000") for a native tooltip. The svg has `role="img"` and an `aria-label` summarising the totals.

## Day-by-day view

Plot: `position:relative; margin:44px 0 32px 40px; flex:1; min-height:170px` (the shared chart plot).

- Gridlines (1px `#E6E6EA`): `1,000` at `top:0`, `500` at `top:50%`; baseline `0` at `top:100%` is **1px ink**. Axis labels are mono 11px muted at `left:-40px`, `top:-8px`.
- **Average line**: 2px `#8E8E98` (neutral, `z-index:2` so it sits above the bars) at `top:46.1%` (average ₹539 of a ₹1,000 scale: `100 − 53.9`).
- 31 columns, `display:flex; gap:4px`, each a `<button>` (`height:100%`, content bottom-aligned, bar centred):
  - bar `width:100%; max-width:24px; height: (value/1000*100)%`.
  - all bars are **ink** (daily spend is money out); hover → `#3B3B42`. Today is not recoloured; its axis label is the marker.
  - future days (19–31): 2px `#E6E6EA` stub, no tooltip.
  - axis labels under days **1, 5, 10, 15, 18, 20, 25, 31** (mono 11px muted, `margin-top:8px`).
  - tooltip text `Oct {day} · ₹{value}`.
- Legend under plot: `margin:0 0 0 40px`, mono 11px muted (shared legend): a 20px `#8E8E98` line + "average ₹539 a day · rent and SIP left out".

Daily values, days 1–18: `240, 370, 340, 530, 420, 350, 850, 380, 910, 620, 970, 440, 730, 480, 570, 740, 380, 389` (sum 9,709 = 39,709 spent − 30,000 rent+SIP).

## State

| State | Type | Default |
|---|---|---|
| `view` | `'flow' \| 'days'` | `'flow'` |

No other state. Everything else is static sample data.

## Responsive notes

- Hero number shrinks with the smaller of width and height (`min(8.6vw, 13vh)`); floor 52px.
- Flow and day panels fill remaining height; on a short window their `min-height` floors (220/170) stop them collapsing and the body scrolls instead.
- Flow below 640px width scrolls horizontally inside its panel.

## Acceptance checklist

- [ ] Hero shows `₹37,591` in ink (black), 300 weight, with a small muted rupee sign.
- [ ] Underlined "₹445 a day" has a 2px accent line.
- [ ] Three links: WATCH has a warning-coloured square; each is ≥44px tall; all go to the right pages.
- [ ] Toggle switches title and chart; default is Flow.
- [ ] Flow ribbons add to 77,300 with the right ones summing visually (available ribbon is the largest, ≈48.6%).
- [ ] The 3 smallest right nodes (Fun, Travel, Bills) are thin but labels never overlap (22px gap).
- [ ] Day chart: 18 ink bars, grey average line at 46.1% from top, hover shows tooltip, keyboard focus does too.
- [ ] At 1280×620 nothing overflows the window; second ledger-math block and description are hidden.

## Addition (designed on the canvas)

A fourth action link sits between `TAG` and `NEXT`: tag `LOOK`, no marker, text **2 messages could not be read**, goes to **Needs a look**.
