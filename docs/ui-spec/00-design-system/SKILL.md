---
name: budget-ui-design-system
description: Shared design system for the Ledger budget tracker UI. Tokens (colour, type, spacing), the app shell (fixed header with icon nav, Account menu and month ruler, aside + main), responsive/scaling rules, shared components (segmented control, stepper, switch, index list, ledger-math block, tooltip, chart primitives), motion, accessibility and the single sample dataset. Read before building any page.
---

# 00 · Design system

Reference sources: every `reference/*.dc.html` repeats the shell; `reference/Main.dc.html` is the cleanest.

## 1. Tokens

### Colour

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#0E0E10` | text, strong rules, primary buttons, bars, past ruler ticks |
| `--text-2` | `#3B3B42` | secondary body text, legends |
| `--muted` | `#6B6B73` | labels, captions, inactive nav |
| `--rule` | `#E6E6EA` | row dividers, section rules |
| `--track` | `#EDEDF1` | every bar track (small and large) |
| `--disabled` | `#CFCFD6` | switch off, input underline, struck-through text |
| `--ruler-future` | `#D9D9DF` | future ruler ticks |
| `--hover-row` | `#FAFAFB` | row hover |
| `--hover-index` | `#F6F6F8` | aside index hover |
| `--surface` | `#FFFFFF` | page background |
| **`--accent`** | **`#00875A`** | the one accent: money in, money you have, within-limit, plus the interface highlight (active nav, links, "today") |
| `--accent-pale` | `#C9EEDD` | big pale page glyph in the aside, unassigned plan segment |
| `--accent-ribbon` | `#D8F3E7` | flow ribbon for "still available"; hover `#B3E6CD` |
| `--accent-wash` | `rgba(0,135,90,0.10)` | area under a line chart |
| `--warn` | `#E9A800` | limit at or above the alert level (yellow), Now alert square |
| `--danger` | `#C93030` | limit exceeded (red), over-assigned, negative remaining |
| `--credit` | `= --accent` | every amount that is money coming in (`+₹50,000`) |
| `--debit` | `= --ink` | every amount that is money going out |

**Heatmap ramp** (category spend is money out, so it is a **neutral grey** ramp, 6 steps light to dark): `#F6F6F8 · #E6E6EA · #C9C9D2 · #8E8E98 · #3B3B42 · #0E0E10`. Steps 4 and 5 take white text, steps 0–3 take ink. Constant rows are neutral `#F3F3F6` with `#3B3B42` text.

**Neutral ramp** (Plan stacked bar, in order): `#0E0E10 #2C2C33 #4A4A53 #6B6B73 #8E8E98 #B1B1BA #CFCFD6 #E3E3E8 #EDEDF1`.

Other greys used once: Now average line `#8E8E98`, day-bar hover `#3B3B42`, carried-over flow node `#9A9AA6`, spent ribbon `#EDEDF1` (hover `#C9CDDB`), secondary line inside dark chart tooltips `#C9C9D2`.

**Alternate accent: Caribbean blue.** Replace emerald with `#007F95`; pale `#BDEAF2`; ribbon `#D2F0F6` (hover `#B2E5EF`); wash `rgba(0,127,149,0.10)`. Nothing else changes (yellow and red stay the same in both themes). Build the accent as a single CSS variable set so this is a one-line swap.

### Colour meaning (applies on every page, no exceptions)

Colour tells the user what a number *is*. Pick the colour by meaning, never by taste.

| Meaning | Colour | Where it appears |
|---|---|---|
| **Money out**: debits, spent, committed payments, planned spend | **Ink (black)** `#0E0E10` | Ledger debit amounts and category spend totals, Plan "spent", Now day-by-day bars, flow "spent" ribbons/nodes, Repeats stems and committed total, Trends "spent" columns, category heatmap (grey ramp), Limits "spent" amount |
| **Money in**: credits, income, carried over, kept, unassigned | **Green** `--accent` `#00875A` | Ledger credits (`+50,000`) and Income total, carried-over and income figures, "= unassigned", Trends "money in" bars and kept figures, Add-credit amount |
| **The balance itself**: available, balance now, new balance, opening balance | **Ink** `#0E0E10` | Now hero number and "= available", Add-credit "balance now", "= new balance" and the success sentence, Setup "opening balance". A balance is a position, not a movement |
| **Limit within bounds** | Green `--accent` | Limits fill when under the alert level (including "Spending fast"), Plan progress under 80% |
| **Limit reached the alert level** (default 80%, user-selectable 70/80/90) | **Yellow** `--warn` `#E9A800` | Limits fill + dot when `spent/limit ≥ alert level`, Plan progress at ≥ 80% |
| **Limit exceeded** | **Red** `--danger` `#C93030` | Limits fill + dot + "over" amount, Plan progress and "left" text when negative, "= over-assigned" |
| Neutral / UI | ink, greys, accent | rules, labels, nav, links, focus ring (accent is also the interface highlight) |

Rules:
- A debit is **never** green and a credit is **never** black.
- Yellow and red appear **only** for limit state. Text that sits next to a yellow/red mark stays ink; only the "over" amount itself turns red.
- "Spending fast" (projected to pass the limit but still under) keeps the **green** fill and shows an outlined yellow dot, so the bar colour always reports where you are **now**.

### Typography: one scale, used everywhere

Load from Google Fonts: `Geist` weights 300/400/500/600 and `Geist Mono` weights 400/500.

Every font size in the UI is one of the **role tokens** below. Define them once as CSS variables (`:root`) and never write a raw pixel font size. If something needs a size, pick the role; do not invent a new one.

```css
:root{
  --fs-label:11px;   --fs-s:13px;    --fs-body:14px;  --fs-title:16px;  --fs-h2:18px;
  --fs-brand:21px;
  --fs-fig-md:clamp(18px,3vh,24px);
  --fs-fig-lg:clamp(22px,3.8vh,32px);
  --fs-lead:clamp(17px,1.4vw,22px);
  --fs-display:clamp(52px,min(8.6vw,13vh),150px);
  --fs-numeral:clamp(44px,8vh,76px);
  --fs-page-title:clamp(26px,4vh,34px);
  --row-pad:clamp(6px,1.3vh,12px);
  --bar-s:4px;  --bar-l:clamp(10px,1.7vh,14px);  --track:#EDEDF1;
}
```

| Token | Size | Weight | Tracking | Family | Used for (every page, always) |
|---|---|---|---|---|---|
| `--fs-display` | clamp 52–150px | 300 | −0.065em | Geist | hero number (Now), amount input and amount on success (Add credit). `₹` is `.38em`, muted, `vertical-align:.95em` |
| `--fs-fig-lg` | clamp 22–32px | 300 | −0.035em | Geist | Limits headline, Trends KPI figures |
| `--fs-fig-md` | clamp 18–24px | 300 | −0.03em | Geist | row amounts: "left to spend" (Limits), planned amount (Plan) |
| `--fs-lead` | clamp 17–22px | 400 | −0.01em | Geist | the sentence under a hero number (Now, Add credit success) |
| `--fs-page-title` | clamp 26–34px | 500 | −0.035em | Geist | aside `h1` |
| `--fs-numeral` | clamp 44–76px | – | – | – | size of the aside page glyph (an icon, not text) |
| `--fs-brand` | 21px | 600 | −0.04em | Geist | `ledger` wordmark (sign-in pages only; the signed-in header has no logo) |
| `--fs-h2` | 18px | 500 (inputs 300) | −0.02em | Geist | section headings; text typed into every underline input |
| `--fs-title` | 16px | 500 | −0.01em | Geist | **row titles** (category / payee / payment names), small-block headings (`Add a limit`, `Recent warnings`), stepper glyphs, heatmap row names |
| `--fs-body` | 14px | 400 / 500 | — | Geist | nav links, body text, chart label names (500), aside index labels, large buttons, action links; **mono row amounts** (500) |
| `--fs-s` | 13px | 400 / 500 | — | Geist or Mono | captions, notes, aside descriptions, status text, small buttons and segmented controls (500), chips, **mono data cells** (tags, spent, left, repeats, next, ledger-math rows), tooltips |
| `--fs-label` | 11px | 400 | +0.06em, uppercase when it is a header | Geist Mono | caps labels and column headers, dates, source codes, axis tick labels, legends, ruler day numbers, chart-label amounts, month text |

Rules that go with the scale:
- **Two families, fixed roles.** Geist for reading text; Geist Mono for labels, codes, dates, tags and all numbers inside lists. Large figures (display, fig-lg, fig-md) are Geist 300.
- **Weights:** 300 for figures and typed input, 400 body, 500 for names/buttons/active values, 600 only for the active index item, the wordmark, and "still available" in the flow.
- Mono numbers use `font-variant-numeric: tabular-nums`.
- Captions and notes are always `--fs-s` muted `#6B6B73`; labels always `--fs-label` muted. Muted text is never a different grey.

Money formatting: rupee sign `₹`, **Indian digit grouping** (`1,25,000`), minus is the true minus `−` (U+2212), credits use `+`.

### Spacing and sizing

| Thing | Value |
|---|---|
| Page horizontal padding | `clamp(20px, 3.5vw, 64px)` |
| Gap between aside and main | `clamp(32px, 4vw, 72px)` (column gap), `24px` row gap when wrapped |
| Body vertical padding | top `clamp(6px, 1.4vh, 12px)`, bottom `clamp(16px, 3vh, 32px)` |
| Aside width | `clamp(208px, 16vw, 264px)` |
| Main minimum before wrapping | `flex: 1 1 640px` |
| Header ruler row padding | `clamp(6px,1.2vh,12px) 0 clamp(20px,3vh,28px)` |
| Rules | 1px, never thicker except active-nav underline (2px) and avg/limit lines (2px) |
| Radius | **0** everywhere |
| Shadows / gradients | none, with one exception: **every bar** (Now day bars, Ledger index bars, Plan line fills, Limits bars, Repeats stems, Trends bars, password strength) uses a **narrow same-hue gradient: a deeper tone at the base or start, the normal brighter tone at the tip or end** (no pastel tints, nothing that reads as a glow or a fade-out). Vertical bars `linear-gradient(0deg, dark, light)`, horizontal `linear-gradient(90deg, dark, light)`. Pairs: ink `#0E0E10 → #4A4A52`, accent `#005C3D → #00A06B`, yellow `#B88400 → #F2B705`, red `#8E1F1F → #DA4444`. Not applied to the Plan split bar (its segments are told apart by shade), the flow-chart nodes, tracks, or the hatched pace blocks |

## 2. App shell (identical on every page)

```
<root height:100vh; overflow:hidden; display:flex; flex-direction:column>
  <header flex:none; padding:0 clamp(20px,3.5vw,64px)>
    <row1 flex wrap; align-items:center; justify-content:space-between; gap:0 32px; border-bottom:1px solid ink>
      nav: 6 links, each with a 16px line icon           gap 0 28px
      right group (gap 12px): "+ Add credit" button      36px high
                              Account button + menu      36px high
    </row1>
    <row2 ruler flex; align-items:flex-end; gap:20px>
      label "day 18 of 31"  (mono 11px, width 92px, flex:none)
      ticks container flex:1; flex; gap:4px; align-items:flex-end; height:18px
    </row2>
  </header>
  <body-scroller flex:1; min-height:0; overflow-y:auto; display:flex; flex-wrap:wrap>
    <aside flex:0 0 clamp(208px,16vw,264px); min-height:0; overflow-y:auto>
    <main  flex:1 1 640px; min-width:0; min-height:0; display:flex; flex-direction:column>
  </body-scroller>
</root>
```

- **Root is exactly the window height** (`100vh`), never `min-height`. Nothing flows out of the page.
- On narrow windows the row wraps: aside stacks above main and the body scroller scrolls.
- Use thin scrollbars on all scroll areas: `scrollbar-width: thin; scrollbar-color: #CFCFD6 transparent`.

### Header: nav

Six links, in order: `Now → /`, `Ledger → /ledger` (carries badge **1**, the "Needs a tag" count), `Plan`, `Limits`, `Repeats`, `Trends`. **There are no sequence numbers.** Each link starts with a 16px line icon (24-unit viewBox, `stroke currentColor`, width 1.7, round caps and joins, `margin-right:8px`) in `#8E8E98`, accent when active.

| Link | Icon path (`d`) |
|---|---|
| Now | `M20 12a8 8 0 1 0-16 0a8 8 0 1 0 16 0Z M11 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0Z` |
| Ledger | `M5 7h14 M5 12h14 M5 17h9` |
| Plan | `M4 4h7v7H4Z M13 4h7v7h-7Z M4 13h7v7H4Z M13 13h7v7h-7Z` |
| Limits | `M4 10h16v4H4Z M15 5v14` |
| Repeats | `M19 12a7 7 0 1 1-2.1-5 M19 4v4h-4` |
| Trends | `M4 20h16 M5 16l4.5-5 3.5 3L19 7` |

- Link padding `16px 0 14px`, `margin-bottom:-1px`, bottom border 2px transparent; **active** = `--ink` text + `2px solid --accent` border + accent icon. `aria-current="page"` on the active link; the `<nav>` is labelled "Main".
- Badge: mono 11px, white on `--accent`, padding `1px 5px`, `margin-left 6px`.
- Child pages light their parent: **Needs a look** lights Ledger. Pages with no parent (Setup guide) and the Add-credit page light no nav item.

### Header: "+ Add credit"

An anchor to `/credit` styled as a button: inline-flex, height 36px, padding `0 16px`, background `--ink`, white text 13px/500. Hover → background `--accent` (`transition .15s`). On the Add-credit page it stays in place with `aria-current="page"` and the accent background (the old "back to now" link is gone; the wordmark and the Now link go back).

### Header: Account menu

Right of "+ Add credit": a 36px button, `padding:0 12px 0 3px`, 1px border (`#CFCFD6`; ink while open or while an account page is showing), containing a 28px square avatar (ink, white mono 11px initial; accent while an account page is showing), the word **Account** (13px/500) and a 12px chevron that rotates 180° when open. `aria-haspopup="menu"`, `aria-expanded`.

Open panel (`role="menu"`, 300px wide, `max-width:calc(100vw - 40px)`, white, 1px ink border, no shadow, drops from `top:calc(100% + 8px)` aligned right, `z-index:31`, enters with a 0.18s fade and 4px rise): identity row (36px avatar, name 14/500, email mono 11 muted, bottom rule `#E6E6EA`) then rows, each 44px high, `padding:10px 16px 10px 13px`, 14px/500 label left and a mono 11px muted hint right, `3px` accent left border on the current page, hover `#F6F6F8`:

| Row | Hint | Goes to |
|---|---|---|
| Profile and preferences | name, alerts, data | `/account` |
| Security | two-step, passkeys | `/account/security` |
| Devices and Telegram | iPhone, bot | `/account/devices` |
| Setup guide | about 15 min | `/setup` |
| Needs a look | 2 messages (live count) | `/ledger/unread` |
| **Sign out** (top border ink) | this browser | sign-in page |

Footer: mono 11px muted, `signed in today · 6:42 pm / renews while you use it`. A transparent full-screen button behind the panel (`position:fixed; inset:0; z-index:30`) closes it on an outside click; **Escape** closes it too (a key handler on the header).

### Header: month ruler

31 ticks (days 1–31), `flex:1`, gap 4px, bottom-aligned:

| Day | Height | Colour |
|---|---|---|
| past (`< today`) | 10px | `--ink` |
| today (18) | 18px | `--accent` |
| future | 6px | `#D9D9DF` |

Day numbers (mono 11px, `margin-top:5px`, centred under the tick) are shown for **1, 10, 20, 31 and today**. Today's label is `--accent`, weight 500.

```js
function ruler(today = 18) {
  return Array.from({ length: 31 }, (_, i) => {
    const d = i + 1, isToday = d === today, past = d < today;
    return {
      day: d,
      showLabel: [1, 10, 20, 31].includes(d) || isToday,
      height: isToday ? 18 : past ? 10 : 6,
      color: isToday ? ACCENT : past ? INK : '#D9D9DF',
    };
  });
}
```

### Aside (the "margin")

Order, top to bottom: **page glyph** → `h1` → description (`.opt`) → page-specific block(s). The glyph is the same icon as the page's nav link, drawn at `--fs-numeral` size (`width` and `height` both `var(--fs-numeral)`, `stroke-width .7`, colour `--accent-pale`, `margin-bottom:calc(var(--fs-numeral) * -0.1)`). Pages without a nav link use their own: Add credit `plus`, Needs a look `question circle`, Account `person`, Security `shield`, Devices `phone`, Setup guide `tick over a line`; the sign-in pages use an arrow, person-plus, padlock and reset arrow. Glyph and title scale with viewport height (see tokens). Description is hidden on short screens (see §3).

### Ledger-math block (used on Now, Plan, Repeats, Add credit, Trends variant)

Mono 13px (`--fs-s`). Rows `display:flex; justify-content:space-between; padding:5px 0`; label `--muted`, value ink. Final row: `margin-top:5px; padding-top:8px; border-top:1px solid ink; font-weight:500` with label prefixed `=` and value in `--accent`. Operator prefixes (`+`, `−`, `÷`) are part of the label text.

## 3. Responsive and scaling rules

The design must adapt to **both** window width and height:

1. **Fluid sizes.** Use `clamp()` with `vw` for horizontal padding, aside width and large text, and with `vh` for vertical padding, numeral/title sizes, row padding, bar thickness.
2. **Flexible regions.** Charts, lists and tables use `flex: 1; min-height: 0` plus a small `min-height` floor (110–220px). They grow on tall windows and shrink on short ones.
3. **Overflow stays inside.** Any list or panel that can exceed its space is `overflow-y: auto`. The root never scrolls.
4. **Optional content hides on short screens**:
   - `@media (max-height: 800px) { .opt { display: none } }`
   - `@media (max-height: 700px) { .opt2 { display: none } }`
   - `.opt` = aside descriptions, Limits "Recent warnings", Add-credit plan switch and footnote.
   - `.opt2` = second ledger-math block, aside notes, Limits "HOW" toggles, Add-credit quick-amount chips and recent credits.
5. **Percent geometry in charts.** Plot containers are `position: relative` with flexible height; gridlines, bars, dots and labels are positioned in **%** of the plot, never fixed px (exception: label/cap offsets such as `+8px`).
6. Respect `prefers-reduced-motion`: disable all animations and transitions.

## 4. Shared components (one definition each, reused on every page)

These are the only versions of each component. A page must not restyle them.

### Row (every list: Ledger, Plan, Repeats, Limits, recent lists)
- Vertical padding `var(--row-pad)` = `clamp(6px, 1.3vh, 12px)`, bottom rule `1px solid #E6E6EA`, hover background `#FAFAFB` (`.12s`).
- Row title `--fs-title` 500, tracking −0.01em. Secondary line `--fs-s` muted, one line, ellipsis.
- Mono data cell `--fs-s`; row amount mono `--fs-body` 500, right-aligned, tabular; credits in `--accent` with `+`.
- Column header above a list: mono `--fs-label` uppercase +0.06em muted, `border-bottom:1px solid #E6E6EA`, `padding:10px 0` (the first rule above a table is 1px ink).

### Section header row (every panel)
`h2` (`--fs-h2`/500) on the left, optional mono `--fs-label` muted caption or a segmented control on the right; `padding-bottom:12–14px`; the block under it starts with a `1px solid ink` rule.

### Progress bar (one component, two sizes)
| | Small `bar-s` | Large `bar-l` |
|---|---|---|
| Height | `4px` | `clamp(10px, 1.7vh, 14px)` |
| Track | `#EDEDF1` | `#EDEDF1` |
| Ends | square | square |
| Used by | Plan "USED" column, Ledger category index | Limits rows |

Fill colour is **semantic and identical everywhere**: `--accent` = within limit, `--warn` = ≥ 80% of the limit (or "close"), `--danger` = over the limit. The exception is a **share bar** (the Ledger index shows each category's share of the largest, not progress): fill ink, accent for the active item. Fills carry the horizontal gradient (dark at the start, normal tone at the end). Fill animation `scaleX` from the left `.9s`; width changes `transition .35s`. An alert/limit **tick** is always 2px ink, extending 4px above and below the track.

### Vertical bars and chart plots (Now day bars, Trends columns)
- Plot: `position:relative; margin:44px 0 32px 40px; flex:1; min-height:150–170px`.
- Gridlines `1px #E6E6EA`; baseline `1px` ink; y labels mono `--fs-label` muted at `left:-40px; top:-8px`; x labels mono `--fs-label` muted `margin-top:8px` under each column.
- Bars have square ends, grow with `scaleY` from the bottom, and **brighten on hover** (`filter:brightness(1.45)`, never a flat colour swap, so the gradient survives). Width: `60%` of the column up to `72px` when there are ≤ 12 columns; `100%` up to `24px` for 31 columns.
- Colour follows meaning: money-out bars (daily spend, "spent") are **ink**; money-in parts ("kept") are **accent**. Stacks put ink (spent) under accent (kept). Each bar uses the narrow same-hue gradient from the *Shadows / gradients* row (dark at the base, normal tone at the tip); an in-progress month adds a hatched block (`repeating-linear-gradient(135deg, colour 0 1.5px, transparent 1.5px 6px)`) separated from the solid part by a 2px gap.
- Line charts: 2px `--accent` line, round joins, `--accent-wash` area, 12px square dots with 2px white border on hover.
- Every column is a `<button>` so the tooltip also shows on keyboard focus.

### Tooltip
Ink background, white `--fs-s` mono text, `padding:8px 12px`, `line-height:1.6`, `white-space:nowrap`, positioned `left:50%; top:-8px; transform:translate(-50%,-100%)`, opacity `0→1` on hover/focus (`.12s`). First line (title) weight 500; secondary lines `#C9C9D2`.

### Legend
Mono `--fs-label` muted, `gap:6px 24px`; swatches are 11–12px squares (or the actual mark: a 2px line, a 2px tick, a bar sample). Appears directly under the section header rule.

### Chart label (flow diagram nodes, timeline stems)
Name `--fs-body` 500 above an amount in mono `--fs-label` muted. The emphasised item uses `--accent` and weight 600.

### Segmented control
`display:flex; border:1px solid ink`; buttons **32px high**, padding `0 16px`, `--fs-s` 500, no border. Active = ink fill + white text; inactive = white + ink. Used on Now, Ledger, Trends, Add credit (all the same height).

### Stepper button
`30×30`, `1px solid ink`, white, glyph `--fs-title`. Hover (enabled) = ink fill + white glyph; disabled = opacity .3. The same size in the aside and in rows.

### Switch
Track `36×20`, knob `14×14` white, `3px` inset, square. On = `--accent`, off = `#CFCFD6`. `role="switch"` + `aria-checked`. Same on every page.

### Index list (aside filters)
Buttons with `padding: clamp(5px,1.1vh,9px) 0 clamp(5px,1.1vh,9px) 12px`, bottom rule `#E6E6EA`, **3px left border** (`--accent` active, transparent otherwise, `margin-left:-3px`), label `--fs-body` (active 600/ink, inactive 400/`#3B3B42`), right value mono `--fs-s` muted. Hover `#F6F6F8`.

### Underline input
No box: `border:0; border-bottom:1px solid #CFCFD6; background:transparent; padding:0`, height `clamp(34px, 5vh, 42px)`, text `--fs-h2` weight 300, label above it mono `--fs-label` caps. The big amount input is the same pattern at `--fs-display` with an ink bottom rule.

### Buttons
- **Small** (header action, Create, Set limit, New repeating payment): `36px`, padding `0 16px`, `--fs-s` 500.
- **Large** (Add credit submit, Back to Now): `44px`, padding `0 28px`, `--fs-body` 500.
- Both: ink background, white text, radius 0, hover `--accent`, disabled opacity .3.

### Chip (tag)
`34px` high, padding `0 14px`, mono `--fs-s`, `1px solid #CFCFD6`; selected = ink fill, white text, ink border; hover border ink.

### Text link
Ink, underline in `--accent`, `text-underline-offset:5px`, hover text → `--accent`; mono `--fs-s` in dense UI, `--fs-body` in prose; min hit height 36–44px.

### Ledger-math block
Mono `--fs-s`; rows `padding:5px 0`, label `#6B6B73`, value ink; final row `border-top:1px solid ink; padding-top:8px; margin-top:5px; weight 500`, label starts with `=`, value in `--accent`.

### Ghost button
Outlined sibling of the small button: `36px`, padding `0 16px`, `--fs-s` 500, `1px solid ink`, white fill, ink text; hover = ink fill + white text; disabled opacity .3. Used for secondary actions in the Account area (`Change password`, `Export`, `Send a test message`). The **bad** variant is the same shape with `#C93030` border and text, and a red fill + white text on hover (`Delete account`, `Unlink`, `Cancel token`, `Sign out all other browsers`). A ghost control that navigates is an `<a>` with the same style.

### Settings row (Account area, Setup)
`display:flex; align-items:center; justify-content:space-between; gap:16px; padding:var(--row-pad) 0; border-bottom:1px solid #E6E6EA`. Left: title `--fs-body` 500 over a `--fs-s` muted line (line-height 1.5, `margin-top:2px`); right: one control (ghost button, switch, text link or a mono value). A row with a mono second line uses `--fs-label`.

### Inline confirmation well
Used for anything that could lock the user out or move data. A grey block (`#F6F6F8`, `padding:14px 16px`, `margin:0 0 var(--row-pad)`) that **opens under its row**, never a modal or pop-up, and enters with `rise`. Contents: one explanatory sentence (`--fs-s`, `#3B3B42`, line-height 1.5), then the **code input** and the confirming button side by side (`gap:12px 20px`, `align-items:flex-end`, wrapping). The button stays disabled until the inputs are valid. The row's own button turns into `Cancel` while the well is open.

### Code input
Underline input at 160px wide, 38px high, `--fs-h2` weight 300, letter-spacing `.32em`, mono placeholder `000000`, `inputmode="numeric"`, `autocomplete="one-time-code"`, non-digits stripped, max 6. Label above: mono caps `AUTHENTICATOR CODE`.

### Status line
A 9px square then one sentence (`--fs-s`): accent square = ok/done, yellow square (pulsing, `wait`) = in progress or paused, red square = stopped/destructive. Always paired with words, never colour alone. `role="status"`.

### Strip links (LOOK, CHECK, WATCH, TAG, NEXT)
A row under a heading: `border-bottom:1px solid #E6E6EA`, items `min-height:44px`, `gap:0 32px`; each item is a mono caps 11px muted tag, a 14px/500 sentence and a trailing arrow (`→` link, `↓/↑` for a toggle that opens a well). Hover = accent.

### Account area (three pages share it)
- **Aside:** page glyph, `h1`, description, then a mono caps header `YOUR ACCOUNT` and the *Index list* of sibling pages (Profile, Security, Devices and Telegram), then a ledger-math style summary (`.opt2`).
- **Main header:** mono caps label (the page's section), `h2` at `--fs-fig-lg` weight 300 tracking −0.035em, a lead sentence `--fs-s` muted (max 680px), then a scroller with `border-top:1px solid ink; padding-top:clamp(10px,2vh,18px)`.
- The Account button in the header is outlined in ink and its avatar turns accent while one of these pages is showing.

### Account menu
Specified under *Header: Account menu*. Rows are 44px, panels never use shadows, Escape and an outside click close it.

### Focus ring
`outline:2px solid --accent; outline-offset:3px` on `a`, `button`, `input` (`:focus-visible`).

## 5. Motion

| Effect | Spec |
|---|---|
| Block entrance (`rise`) | opacity 0→1, translateY 8→0, `.6–.8s cubic-bezier(.2,.8,.2,1)` |
| Vertical bars | `scaleY(0→1)`, origin bottom, `.7–.8s` same easing, stagger 20–60ms per bar |
| Horizontal bars | `scaleX(0→1)`, origin left, `.9s` |
| Line charts | `clip-path: inset(0 100% 0 0) → inset(0 0 0 0)`, `1.2–1.4s cubic-bezier(.3,.7,.2,1)` |
| Flow diagram | opacity fade `1s` |
| Width changes (limits fill, plan segments) | `transition: width .35s cubic-bezier(.2,.8,.2,1)` |
| Loading text | opacity pulse `.35 → 1 → .35`, 1s infinite |

## 6. Shared sample dataset (single source of truth)

Use these numbers on every page so totals reconcile.

**Month:** October 2026, day 18 of 31, 13 days left.

**Balance:** carried over `27,300` + income `50,000` − spent `39,709` = available **`37,591`**. Safe to spend: plan left `5,791` ÷ 13 days = **`445`** per day.

**Plan (₹50,000 to plan, 45,500 assigned, 4,500 unassigned):**

| Category | Planned | Spent | Left |
|---|---|---|---|
| Rent | 20,000 | 20,000 | 0 |
| SIP | 10,000 | 10,000 | 0 |
| Food | 8,000 | 5,420 | 2,580 |
| Travel | 3,000 | 1,350 | 1,650 |
| Bills | 2,500 | 1,299 | 1,201 |
| Fun | 2,000 | 1,640 | 360 |

**Six months:**

| Month | Income | Spent | Kept | Month-end balance |
|---|---|---|---|---|
| May | 50,000 | 41,200 | 8,800 | 6,400 |
| Jun | 50,000 | 44,800 | 5,200 | 11,600 |
| Jul | 52,000 | 47,300 | 4,700 | 16,300 |
| Aug | 50,000 | 43,100 | 6,900 | 23,200 |
| Sep | 50,000 | 45,900 | 4,100 | 27,300 |
| Oct (so far) | 50,000 | 39,709 | 10,291 | 37,591 (today) |

Averages (May–Sep, full months): spend **44,460**, kept **11.8%**; balance growth since end of May **+31,191**.

**Recurring:** Rent 20,000 (1st), Nifty 50 index fund 10,000 (5th), Cloud storage 130 (12th), Netflix 649 (17th). Committed = **30,779**/month.

**Credits:** Salary +50,000 on the 1st of Aug, Sep, Oct.

**Capture and account (used by Needs a look, Security, Devices):** two unread messages (OCT 17 amount found, direction unclear; OCT 14 no amount found); tracked account savings ending 4821; ingest token `ledg_live_8f3a…b605` made Oct 02; Telegram id `••••4821` linked Oct 04, bot signed in since today 6:31 pm; last balance check today 6:50 pm matched; three sessions and two passkeys as listed in the Security spec; export file `ledger-export-2026-10-18.zip`.

**Pace (October, day 18):** flexible spend so far ÷ 18 × 31, rounded to ₹10, plus the fixed Rent and SIP (30,000). Food 9,330, Travel 2,330, Bills 2,240, Fun 2,820; total 46,720; kept at that pace 3,280.

Page-specific datasets (ledger rows, daily spend, category-by-month) are listed in each page spec.

## 7. Accessibility

- Real `<button>`, `<a href>`, `<input>` + `<label>` (visually hidden labels allowed). No clickable divs.
- Charts: ribbons, bars and lines are decorative-plus-tooltip; give each chart `role="img"` with an `aria-label` that states the totals, or provide the same numbers in text nearby.
- Colour is never the only signal. Status always carries words ("Close to the limit"), and dots pair with text.
- Text contrast ≥ 4.5:1: ink/white, `--muted #6B6B73` on white (5:1), accent `#00875A` on white (4.55:1), white on accent (4.55:1).
- Touch/click targets ≥ 36px (44px for primary actions).
- Every chart column is a button, so the tooltip appears on keyboard focus as well as hover, and every number a tooltip shows is also on the page (a label under the column, a list, or the Setup/Ledger rows).
- The Account menu is `role="menu"` with `aria-haspopup` and `aria-expanded` on its button; Escape closes it and returns focus to the button.
- Inline confirmation wells are not dialogs: they sit in the reading order right after the row that opened them.
- Status squares always have text beside them; `role="status"` on lines that appear after an action.
- Gradient bars keep the same contrast as the flat colour they replace (the light end is never paler than the normal tone).

## 8. Suggested component map (React)

```
<AppShell active="now">           header + ruler + aside/main slots
  <Header/> <MainNav icons/> <MonthRuler today={18}/> <AddCreditButton/> <AccountMenu/>
  <Aside glyph title description>…</Aside>
  <Main>…</Main>
<AuthShell>                       sign-in header (wordmark only), aside + main
<AccountAside/> <AccountMain/>    shared by Profile, Security, Devices
primitives: Segmented, Stepper, Switch, IndexList, LedgerMath, UnderlineInput,
            PrimaryButton, GhostButton, TextLink, MonoLabel, Tooltip,
            SettingsRow, ConfirmWell, CodeInput, StatusLine, StripLink
charts:     FlowDiagram, DayBars, InOutBars (Trends), LimitBar, Lollipop,
            GradientBar (one helper: colour name + direction -> CSS gradient)
data:       sample.ts (section 6), money.ts (formatINR, indianGroup)
```

`money.ts`:

```ts
export const inr = (n: number) => '₹' + Math.abs(n).toLocaleString('en-IN');
export const signed = (n: number) => (n < 0 ? '−' : '+') + '₹' + Math.abs(n).toLocaleString('en-IN');
```

## 9. Acceptance checklist (shell)

- [ ] Root height equals the window; no page-level scrollbar at any size from 1100×620 to 2560×1440.
- [ ] Header stays fixed; only the body area scrolls when content cannot fit.
- [ ] Active nav item has a 2px accent underline and accent icon; Ledger carries the badge `1`. There are no sequence numbers and no logo in the signed-in header.
- [ ] The Account button opens a menu with six rows and a footer; Escape and an outside click close it.
- [ ] Ruler shows 31 ticks, 17 ink (past), 1 tall accent (today), 13 grey (future); labels at 1, 10, 18, 20, 31.
- [ ] All radii are 0; no shadows; the only gradients are the narrow same-hue bar shades.
- [ ] Below 800px height `.opt` content disappears; below 700px `.opt2` content disappears.
- [ ] Colour meaning holds on every page: debits/spent and every balance are ink, credits/income/kept are green, limits go green → yellow (≥ alert level) → red (exceeded). No debit is green and no credit is black.
- [ ] Accent swap works by changing only the accent variables.

## 10. States: empty, loading, error (apply on every page)

Every list and chart needs these three states. They use only the components above.

| State | Rule | Copy pattern |
|---|---|---|
| **Empty (first run)** | Keep the page frame, aside and headings. Replace the panel content with one centred muted line (`--fs-body`, `#6B6B73`, `padding: clamp(24px,5vh,48px) 0`) and, where an action exists, one small primary button or text link below it. No illustrations. | Say what will appear and how it gets there: Ledger "Nothing yet. Bank messages from your phone land here." · Plan "Nothing planned yet. Type a tag to create your first category." · Limits "No limits yet. Add one below." · Repeats "No repeating payments yet." · Trends "Trends appear after your first full month." · Needs a look "All sorted. Messages the app cannot read will wait here." |
| **Loading** | Keep the previous render at reduced opacity (`.5`) and add a mono muted line with a pulsing label (`wait`, `loading older entries…`). No skeleton blocks, no spinner, no layout jump. | "loading…" in the place the content will appear |
| **Error** | A status line with a **red** square and a plain sentence, plus one `Try again` text link. Never show codes or stack traces. Keep any typed input. | "Could not reach the server. Your entry is kept. Try again." |

Specific cases:
- **Numbers with no data** show `—` (em dash) in the figure position, never `0`, and the note line says why ("no full month yet").
- **Month in progress** is never presented as final: hatched block, "pace" label, or the word "so far".
- **Sign-in and Account pages:** form errors appear under the field in red with a red square, once per submit; the primary button stays enabled so the user can retry; lockout copy says how long.
- **Offline or stale data:** mono muted line under the header ruler, "showing data from 6:42 pm".

## 11. Copy and number rules

- **Plain words.** "Needs a tag", "Needs a look", "Money in and out", "kept", "heading for". Avoid jargon (no "transaction", "reconcile", "ingest" in the interface; use "payment", "check", "phone").
- **Sentence case** everywhere except mono caps labels (`UNREAD MESSAGES`). Buttons name the result: `Add to the ledger`, `Make the file`, not `Submit`.
- **Money:** `₹` then Indian grouping (`₹1,25,000`); lists omit the symbol and use a sign (`−386`, `+50,000`, true minus `−` not hyphen); compact axis labels use `K` (`41.2K`); percentages one decimal in stats (`11.8%`), whole numbers in verdicts (`23%`).
- **Dates and times:** `OCT 18` in lists (mono caps), `today 6:42 pm` in prose, `Oct 25` in sentences. India time only.
- **No bank detail in notifications.** Telegram and any other outside channel say "Money out · 6:42 pm"; amounts and payees appear only in the web app or after Reveal.
- **Balances are ink, money moving in is green, money moving out is ink** (see *Colour meaning*).
- **Destructive actions** are red ghost buttons, name what will be lost, and say how to undo (or that they cannot be undone).
