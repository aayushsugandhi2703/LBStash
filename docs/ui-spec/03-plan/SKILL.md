---
name: budget-ui-plan
description: Build the "03 Plan" monthly allocation page of the Ledger budget tracker: money-to-plan stepper, assigned/unassigned arithmetic, stacked split bar, per-category planned amount steppers with spent/left/progress, and dynamic category creation from typed tags. Matches reference/Plan.dc.html.
---

# 03 · Plan

Reference: `reference/Plan.dc.html` · Route `/plan` · Requires `00-design-system`.

**Purpose.** The user states how much money they have to plan this month and splits it across categories. New categories appear simply by typing a tag.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `Plan` icon / `Plan` |
| Description (`.opt`) | "Decide where every rupee of October goes. Tags you type become categories." |
| Ledger-math (`margin-top:28px`) | row 1: `to plan` + **[−] value [+]** stepper (30px squares, value min-width 52px right-aligned, ±5,000 per press); row 2: `− assigned {sum}`; final row: `= unassigned {n}` (accent) or `= over-assigned {n}` (danger) when negative |
| Note (`.opt2`, `margin-top:24px`) | top rule `#E6E6EA`, `padding-top:12px`, 13px muted: "Unspent money carries into November. Over-assigning is allowed, but flagged." |

### Main (flex column)
1. **Heading row**: `h2` "How October is split" (18px/500) + mono 11px muted "blue is money not yet given a job" (use the accent colour name that matches your theme, e.g. "green is money not yet given a job").
2. **Split bar**: `display:flex; gap:2px; height:32px; background:#F3F3F6`. One segment per category with `background` from the neutral ramp in order, `width = planned / max(total, assigned) * 100%` (`transition width .35s`). After them one **free segment**, `background:#C9EEDD` (accent-pale), `width = unassigned / max(total, assigned)` (0 when unassigned ≤ 0).
3. **Table** (`margin-top:22px; flex:1; min-height:180px`, block `min-width:700px`, horizontal scroll if narrower):
   - Header: mono 11px caps muted, `border-top:1px solid ink`, `border-bottom:1px solid #E6E6EA`, padding 10px 0, gap 20px. Columns: `CATEGORY` 140px · `PLANNED` 190px centred · `SPENT` 70px right · `LEFT` 80px right · `USED` flex (min 70px).
   - Body: scroll panel `flex:1; min-height:120px; overflow-y:auto`. Row: `display:flex; align-items:center; gap:20px; padding: var(--row-pad) 0; border-bottom:1px solid #E6E6EA`; hover `--hover-row`; entrance animation `pop` (opacity + translateY −4→0, .3s).

     | Cell | Spec |
     |---|---|
     | Category | 10px square swatch (ramp colour by row index) + name 16px/500 (ellipsis) |
     | Planned | 30px stepper `−` · amount `--fs-fig-md`/300 tabular (tracking −0.03em) · 30px stepper `+`, `justify-content:space-between`; ±500 per press; `−` disabled at 0 |
     | Spent | mono 13px **ink** (money out) |
     | Left | mono 13px/500; ink normally, **danger** when negative (shown with `−`) |
     | Used | the shared small bar: 4px track `#EDEDF1`, 4px fill; width `min(100, spent/planned*100)%`; fill `--accent` (green) under 80%, `--warn` (yellow) at ≥ 80%, `--danger` (red) when over; `transition width .35s` |

4. **Add a category** (`margin-top:20px`, flex wrap, gap 12px 40px, align end):
   - Left (max-width 420px): mono caps label `NEW CATEGORY · JUST TYPE A TAG`, then an underline row (`border-bottom:1px solid ink`): input (the shared underline input: 18px/300, height `clamp(34px,5vh,42px)`, placeholder `#gym`) + ink button `Create` (36px high, 13px/500).
   - Right: up to three suggestion links `+ #gym`, `+ #gifts`, `+ #pets` (mono 13px, underlined accent, min-height 44px). A suggestion disappears once that category exists.

## Data

```ts
total = 50000
lines = [
  { id:1, name:'Rent',   planned:20000, spent:20000 },
  { id:2, name:'SIP',    planned:10000, spent:10000 },
  { id:3, name:'Food',   planned:8000,  spent:5420  },
  { id:4, name:'Travel', planned:3000,  spent:1350  },
  { id:5, name:'Bills',  planned:2500,  spent:1299  },
  { id:6, name:'Fun',    planned:2000,  spent:1640  },
]
```
Initial derived: assigned 45,500, unassigned 4,500.

## Behaviour

```ts
assigned   = sum(lines.planned)
unassigned = total - assigned           // may be negative
base       = max(total, assigned, 1)    // denominator for the split bar
remaining(l) = l.planned - l.spent
pct(l)     = l.planned > 0 ? min(100, l.spent / l.planned * 100) : 0
```
- Total stepper: `total = max(0, total ± 5000)`.
- Planned stepper: `planned = max(0, planned ± 500)`.
- **Add category**: strip every `#`, trim; if empty do nothing; name = first letter upper-case + rest lower-case; ignore if a line already has that name (case-insensitive) or there are already 9 lines (the ramp length); otherwise append `{ id: next, name, planned: 0, spent: 0 }`, clear the input. Enter-key or the Create button; chips call the same function with their name.
- Over-assigned never blocks anything; it only recolours the unassigned figure to danger.

## Responsive notes

- Row list is the only growing region; adding categories makes it scroll inside its own panel.
- The add-category row wraps under itself on narrow widths; the suggestions drop below the input.

## Acceptance checklist

- [ ] Initial: total 50,000, assigned 45,500, `= unassigned 4,500` in accent; split bar shows six dark-to-light segments plus a pale accent tail of 9%.
- [ ] Pressing total `+` three times gives 65,000 and widens the pale tail.
- [ ] Pressing Fun `+` until planned exceeds total makes the line read `= over-assigned` in danger and the free segment disappears.
- [ ] Food `−` twice → planned 7,000, left 1,580.
- [ ] Typing `#Gym` → `Create` adds a "Gym" row with 0 planned, 0 spent, and removes the `+ #gym` suggestion.
- [ ] Planned `−` is disabled at 0.
