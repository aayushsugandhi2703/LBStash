---
name: budget-ui-ledger
description: Build the "02 Ledger" transactions page of the Ledger budget tracker: category index with mini spend bars and counts, source filter, column-headed transaction list in a scroll panel with lazy loading (scroll to load older entries plus a fallback button), tag-it links for untagged debits. Matches reference/Transactions.dc.html.
---

# 02 · Ledger

Reference: `reference/Transactions.dc.html` · Route `/ledger` · Requires `00-design-system`. Nav badge `1` is shown on this item everywhere.

**Purpose.** Every debit the phone captured and every credit the user added, filterable by category and source.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `Ledger` icon / `Ledger` |
| Description (`.opt`) | "Every debit your phone caught and every credit you added." |
| Index header | mono 11px caps muted `BY CATEGORY · OCT TOTAL`, `margin-top:24px`, `padding-bottom:7px`, `border-bottom:1px solid ink` |
| Category index | an **Index list** (design-system §4), nine items below |

Category index items (label · right value · mini bar):

| Key | Label | Right value | Mini bar |
|---|---|---|---|
| `All` | All | `18 entries` | none |
| `needs tag` | Needs a tag | `1` | none, label in accent |
| `food` | Food | `5,420` | 5,420 / 20,000 |
| `fun` | Fun | `1,640` | 1,640 / 20,000 |
| `travel` | Travel | `1,350` | 1,350 / 20,000 |
| `bills` | Bills | `1,299` | 1,299 / 20,000 |
| `sip` | SIP | `10,000` | 10,000 / 20,000 |
| `rent` | Rent | `20,000` | 20,000 / 20,000 |
| `income` | Income | `+50,000` | none |

Right values are coloured by meaning: category spend totals ink (money out), `Income` `+50,000` green, `All` and `Needs a tag` counts muted.

Mini bar: below the label, `margin-top:6px`, track `var(--bar-s)` (4px) `#EDEDF1`, fill 4px ink (accent when that item is active), width `max(1%, value/20000)`. The values are month totals; the list shows a subset of rows (the full month has 61), so they do not equal the visible rows.

### Main
1. **Top row** (`border-bottom:1px solid ink; padding-bottom:12px`): left, mono 13px muted `showing {shown} of {matching} · oct 2026`; right, a **segmented control** `All | Auto | Repeat | Manual | Unaccounted` (32px high, the shared segmented control).
2. **Column header** (inside a block with `min-width:640px`, horizontal scroll if narrower): mono 11px caps muted, `border-bottom:1px solid #E6E6EA`, gap 20px:

   | Column | Width | Align |
   |---|---|---|
   | DATE | 58px | left |
   | WHAT | flex | left |
   | TAG | 120px | left (holds `tag it` and, on an Unaccounted row, `split`) |
   | SOURCE | 104px | left |
   | AMOUNT | 108px | right |

3. **Scroll panel** `flex:1; min-height:150px; overflow-y:auto; border-bottom:1px solid #E6E6EA`, rows below.
4. Caption under the list, mono 11px muted: "scroll the list to load older entries".

### Row
`display:flex; align-items:center; gap:20px; padding: var(--row-pad) 12px var(--row-pad) 0; border-bottom:1px solid #E6E6EA`; hover `--hover-row`; each row runs the `rise` entrance.

| Cell | Spec |
|---|---|
| Date | mono 11px muted, e.g. `OCT 18` |
| What | name 16px/500 tracking −0.01em; below it the note 13px muted, single line with ellipsis |
| Tag | mono 13px `#food`; **untagged**: accent mono 13px/500 underlined link `tag it` (min-height 32px) |
| Source | mono 11px muted tracking .04em: `AUTO`, `REPEAT` or `MANUAL` |
| Amount | mono 14px/500 tabular right-aligned; debits ink `−386`, credits accent `+50,000` (no ₹ in rows) |

## Data (18 rows, newest first)

| Date | Name | Note | Tag | Source | Amount |
|---|---|---|---|---|---|
| OCT 18 | Swiggy | “#food dinner” | food | AUTO | −386 |
| OCT 18 | Ramesh Kumar | UPI · no note was written | **none** | AUTO | −450 |
| OCT 17 | Uber | matched rule: uber | travel | AUTO | −214 |
| OCT 17 | Netflix | monthly rule | fun | REPEAT | −649 |
| OCT 16 | Zepto | “#food groceries” | food | AUTO | −612 |
| OCT 15 | Airtel | same payee as last month | bills | AUTO | −299 |
| OCT 14 | BookMyShow | “#fun movie” | fun | AUTO | −540 |
| OCT 12 | Rapido | matched rule: rapido | travel | AUTO | −136 |
| OCT 10 | BESCOM | “#bills electricity” | bills | AUTO | −1000 |
| OCT 09 | Third Wave Coffee | “#food” | food | AUTO | −280 |
| OCT 08 | Chai Point | “#food chai” | food | AUTO | −89 |
| OCT 07 | Ola | matched rule: ola | travel | AUTO | −178 |
| OCT 06 | DMart | “#food monthly” | food | AUTO | −1240 |
| OCT 05 | Nifty 50 index fund | monthly rule | sip | REPEAT | −10000 |
| OCT 04 | Spotify | same payee as last month | fun | AUTO | −119 |
| OCT 03 | Blinkit | “#food” | food | AUTO | −322 |
| OCT 01 | Rent | monthly rule | rent | REPEAT | −20000 |
| OCT 01 | Salary | credit you entered | income | MANUAL | +50000 |

The amounts in the table are written plainly for readability. In the UI they use Indian grouping, for example `−1,000`, `−10,000`, `−20,000`, `+50,000`.

Credits captured from a bank message appear in the same list with no tag and the same accent `tag it` link (chips on tagging: `#salary`, `#refund`, `#gift`, `#transfer`). The sample data shows salary as a hand-added credit; both kinds look identical apart from the SOURCE column (`AUTO` or `MANUAL`).

Note text conventions: `“#tag text”` = the user's own GPay note; `matched rule: x` = learned keyword rule; `same payee as last month` = payee memory; `monthly rule` = recurring; blank note + no tag = untagged.

## State and behaviour

| State | Default | Notes |
|---|---|---|
| `cat` | `'All'` | category index selection |
| `src` | `'All'` | source segmented selection (`All`, `AUTO`, `REPEAT`, `MANUAL`) |
| `count` | `8` | rows currently rendered |
| `loading` | `false` | true during the 600ms fake fetch |

```ts
filtered = rows.filter(r => (cat==='All' || key(r)===cat) && (src==='All' || r.src===src));
shown    = filtered.slice(0, count);
key(r)   = r.tag === null ? 'needs tag' : r.tag;
```

- Changing category or source **resets `count` to 8**.
- **Lazy load:** `onScroll` on the panel; when `scrollTop + clientHeight >= scrollHeight − 30` and not loading and `count < filtered.length` → `loading = true`, after **600ms** `count += 5`, `loading = false`.
- **Fallback button:** while `count < filtered.length` and not loading, show a centred mono 13px underlined button `load older entries ↓` at the end of the list. It calls the same loader. This is required: on tall windows the list may not overflow, so scroll alone could never load more.
- While loading show mono 13px muted pulsing text `loading older entries…`.
- When everything is shown and `filtered.length > 8`, show `that's everything for this view`.
- If `filtered` is empty show `Nothing matches this view.` centred, muted.
- Counter text: `showing {shown.length} of {filtered.length} · oct 2026`.

In production replace the timeout with a paginated fetch and append the returned page.

## Responsive notes

- Panel height is `flex:1`, so it fills whatever remains below the column header; floor 150px.
- Row padding and index-item padding scale with viewport height via `clamp()`.
- Table min-width 640px; narrower screens scroll the block horizontally.

## Acceptance checklist

- [ ] 18 rows exist; 8 render initially; scrolling to the bottom (or clicking the button) adds 5 per load with the loading text.
- [ ] Filtering "Needs a tag" shows exactly Ramesh Kumar with the accent `tag it` link.
- [ ] Filtering "Income" shows Salary with `+50000` in accent.
- [ ] Source filter and category filter combine (AND).
- [ ] Active index item has a 3px accent left border, semibold label, accent mini-bar.
- [ ] No horizontal scrolling at ≥ 1100px width; no page-level scroll anywhere.

## Additions (designed on the canvas; read with `reference/Transactions.dc.html`)

These come from the balance check (README section 3.6 and flow 10.9).

- **Strip above the top row** (`border-bottom:1px solid #E6E6EA`, links `min-height:44px`, `gap 0 32px`, like the action links on Now): `LOOK  2 messages could not be read →` goes to **Needs a look**; `CHECK  Compare with your bank's balance ↓` toggles the check panel.
- **Check panel** (grey well `#F6F6F8`, padding `14px 16px`): mono label `BALANCE IN YOUR BANK APP RIGHT NOW · ₹`, underline input (mono 18px light, 200px), `Check` button (36px, disabled at 0), caption `the ledger says ₹37,591`. Result line with a 9px square: green **matches the ledger**; yellow **gap** with the sentence "₹180 left your account and no message explains it. It is booked as an Unaccounted entry after 6 hours, unless the missing message arrives first." plus `Book it now` (primary) and `Wait for the message` (text link); a pulsing yellow square while waiting; green **booked** once booked. The demo accepts any amount; typing 37,411 shows the 180 gap.
- **Unaccounted row:** a 7px `--warn` square before the name, source `UNACCOUNTED`, the same `tag it` link, and a `split` link. Booking sets the ledger balance to the bank's figure and raises the "Needs a tag" count.
- **Split panel** (same well): label `SPLIT THE UNACCOUNTED ₹{left}`, `THIS PART · ₹` input, `GOES TO` segmented tag choice (Food, Travel, Fun, Bills), `Split` (disabled unless 0 < part < left), `Close`; caption `the rest, ₹{rest}, stays Unaccounted`. A split adds a tagged row "Split from Unaccounted"; the remainder stays one Unaccounted row until it is fully split.

Acceptance: [ ] Checking 37,591 says it matches. [ ] Checking 37,411 offers to book ₹180; booking adds a yellow-marked Unaccounted row of −180 and the ledger caption changes to 37,411. [ ] Splitting 100 to Food leaves ₹80 Unaccounted. [ ] The Unaccounted filter shows only those rows.
