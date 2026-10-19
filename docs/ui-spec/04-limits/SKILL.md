---
name: budget-ui-limits
description: Build the "04 Limits" budgets page of the Ledger budget tracker: plain-language headline, one progress bar per category with an alert tick, status words (On track / Spending fast / Close to the limit / Over the limit), month-end pace sentence, alert-level selector, add-limit form and recent warnings. Fluid height with internal scrolling. Matches reference/Budgets.dc.html.
---

# 04 · Limits

Reference: `reference/Budgets.dc.html` · Route `/limits` · Requires `00-design-system`.

**Purpose.** Show, in plain words and one simple bar per category, how close each spending limit is, and warn before it is crossed. Deliberately **not** a complex chart: the bar's full length is the limit, the black tick is the alert level, everything else is a sentence.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `Limits` icon / `Limits` |
| Description (`.opt`) | "A spending ceiling for each category. You get a warning before you reach it." |
| Header | mono 11px caps muted `WARN ME WHEN A LIMIT IS` (`margin-top: clamp(12px,2.6vh,24px)`) |
| Alert-level index list | `70% used · early warning`, `80% used · balanced` (default), `90% used · last minute`. Index-list styling (3px left border, active semibold) |
| `HOW` block (`.opt2`) | header `HOW`; two switch rows (padding 9px 0, rule `#E6E6EA`, 36×20 switch): `Send alerts to Telegram` (on), `Warn if pace runs over` (on). Alerts are delivered only through Telegram |

### Main (flex column, `min-height:0`)
1. **Headline block** (`flex:none`, `rise`): mono 11px caps muted `13 DAYS LEFT IN OCTOBER`; then the headline, `var(--fs-fig-lg)` = `clamp(22px, 3.8vh, 32px)`, weight 300, tracking −0.035em, `line-height 1.15`.
2. **Legend row** (`flex:none`; `margin-top: clamp(8px,1.6vh,14px)`; `border-top:1px solid ink`; `padding-top: clamp(6px,1.2vh,12px)`; mono 11px muted; gap 6px 24px): `[18×8 #EDEDF1 swatch] the bar's full length is your limit` `[2×14 ink swatch] your alert level (80%)` (percentage follows the selected level), then the **colour key**: `[11px green] within the limit`, `[11px yellow] close to it (80%+)`, `[11px red] over the limit`.
3. **Rows panel** `flex:1 1 0; min-height:0; overflow-y:auto; margin-top:4px; display:flex; flex-direction:column`.
4. **Bottom row** (`flex:none; margin-top: clamp(8px,1.6vh,18px)`, flex wrap gap 16px 48px): **Add a limit** and, `.opt`, **Recent warnings**.

### Limit row
Container: `flex:1 1 auto; min-height:0; max-height:190px; padding: var(--row-pad) 0; border-bottom:1px solid #E6E6EA; display:flex; flex-direction:column; justify-content:center`; hover `--hover-row`. Rows share the available height, never exceed 190px.

1. **Top line** (`display:flex; align-items:baseline; justify-content:space-between; gap:6px 16px; flex-wrap:wrap`):
   - left: name `--fs-title` (16px)/500 tracking −0.01em, then status (dot 9px + text 13px/500 `#3B3B42`);
   - right: amount left `--fs-fig-md`/300 tabular + label 13px muted (`left to spend`, or `over` when negative). The amount is ink; **when the limit is exceeded it turns red `--danger`**.
2. **Bar**: `position:relative; height: var(--bar-l) = clamp(10px, 1.7vh, 14px); background:#EDEDF1; margin-top: clamp(6px,1.4vh,12px)`.
   - Fill: `position:absolute; left:0; top:0; height:100%; max-width:100%; width: min(100, pct)%`, grow animation `scaleX` from left `.9s`, `transition width .35s, background .2s`.
   - Alert tick: `position:absolute; top:-4px; bottom:-4px; width:2px; margin-left:-1px; background: ink; left: {level}%`, `transition left .35s`.
3. **Caption** (`display:flex; justify-content:space-between; flex-wrap:wrap; gap:4px 16px; margin-top: clamp(4px,1vh,8px); 13px; muted`):
   - left: `**₹1,640** of ₹2,000 spent · 82%` (amount ink/500);
   - right: `At this pace you reach ₹2,820 by month end, ` + `₹820 over` (danger/500) **or** `₹260 under` (ink/500).

### Bottom row
- **Add a limit** (`h3` 16px/500): top rule 1px ink; flex wrap, gap 10px 14px, align end; two underline inputs (`CATEGORY OR TAG` placeholder `#gym` flex 1 1 120px; `MONTHLY LIMIT` placeholder `₹2,000` flex 1 1 100px; height `clamp(34px,5vh,42px)`, 18px/300: the shared underline input) and a primary `Set limit` button (36px).
- **Recent warnings** (`.opt`): `h3` (`--fs-title`, 16px/500); list in a scroller `max-height:96px` with rows `padding:7px 0; border-bottom:1px solid #E6E6EA`: mono date (52px) · text 14px/500 · mono 11px muted numbers.
  - `OCT 17 · Fun passed 80% · 1,600 / 2,000`
  - `SEP 27 · Food went over its limit · 8,350 / 8,000`
  - `SEP 22 · Food passed 80% · 6,500 / 8,000`
  - `SEP 19 · Fun passed 80% · 1,620 / 2,000`

## Data

```ts
items = [
  { name:'Fun',    spent:1640, limit:2000 },
  { name:'Food',   spent:5420, limit:8000 },
  { name:'Bills',  spent:1299, limit:2500 },
  { name:'Travel', spent:1350, limit:3000 },
]
level = 80   // 70 | 80 | 90, state
```

## Logic (exact)

```ts
const DAYS_ELAPSED = 18, DAYS_IN_MONTH = 31;
pct       = spent / limit * 100
projected = Math.round(spent / DAYS_ELAPSED * DAYS_IN_MONTH / 10) * 10   // nearest 10
left      = limit - spent
diff      = projected - limit

status:
  spent >= limit        → 'Over the limit'      kind 'over'
  else pct >= level     → 'Close to the limit'  kind 'near'
  else projected>limit  → 'Spending fast'       kind 'pace'
  else                  → 'On track'            kind 'ok'
```

| Kind | Dot | Fill colour |
|---|---|---|
| over | filled `--danger` (red `#C93030`) | `--danger` |
| near (≥ alert level) | filled `--warn` (yellow `#E9A800`) | `--warn` |
| pace | white with 2px `--warn` border | `--accent` (green, still under the limit) |
| ok | filled `--accent` | `--accent` |

- Rows are **sorted by `pct` descending**.
- `needs` = rows with kind `near` or `over`. Headline:
  - `needs.length === 0` → "All four limits are on track."
  - `1` → "{Name} needs a look. The other {n−1} are fine."
  - `> 1` → "{n} limits need a look: {A} and {B}."
- Sample outputs at level 80: headline "Fun needs a look. The other 3 are fine."; rows in order Fun (82%, ₹360 left, Close to the limit, reach ₹2,820, ₹820 over), Food (68%, ₹2,580, Spending fast, ₹9,330, ₹1,330 over), Bills (52%, ₹1,201, On track, ₹2,240, ₹260 under), Travel (45%, ₹1,650, On track, ₹2,330, ₹670 under).
- Changing the level moves every tick, re-evaluates statuses and updates the legend text and headline. At 90%, Fun becomes "Spending fast".

## Responsive notes (this page overflowed before; keep these)

- Root is `100vh` with `overflow:hidden`; **only the rows panel scrolls** if the window is very short.
- All vertical paddings, font sizes and bar thickness use `clamp(…vh…)`.
- `.opt` (description, Recent warnings) hides under 800px height; `.opt2` (HOW toggles) under 700px.
- Rows have `min-height:0` so they compress before scrolling.

## Acceptance checklist

- [ ] Four rows, ordered Fun, Food, Bills, Travel at level 80.
- [ ] Fun's bar is 82% filled in warn colour with the ink tick at 80%, so the fill passes the tick.
- [ ] Food's fill is accent (68%) with dot outlined in warn and the text "Spending fast".
- [ ] "₹820 over" is danger-coloured; "₹260 under" is ink.
- [ ] Level 70 flips Food (68%) → still "Spending fast" (below 70) and moves ticks to 70%; level 90 flips Fun to "Spending fast".
- [ ] Colour rules: green fill under the alert level, yellow fill at ≥ alert level (Fun at 82%), red fill and red "over" amount once spent ≥ limit (try Food at 8,350 / 8,000).
- [ ] The legend shows the three-colour key; the yellow entry text follows the selected level (`close to it (80%+)`).
- [ ] Nothing extends past the window at 1280×600 or 2560×1440; bars never exceed their track.
- [ ] Bottom form fits in one row ≥ 700px wide.
