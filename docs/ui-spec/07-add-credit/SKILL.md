---
name: budget-ui-add-credit
description: Build the "+ Add credit" page of the Ledger budget tracker: giant live-formatted amount input, quick-add amounts, source tag chips with on-the-spot new tags, date quick-picks, optional note, add-to-plan switch, live ledger arithmetic in the margin, and a success state. Matches reference/Credit.dc.html.
---

# 07 · Add credit

Reference: `reference/Credit.dc.html` · Route `/credit` · Requires `00-design-system`. Opened from the header `+ Add credit` button on every page.

**Purpose.** Credits that arrive as a bank message are captured automatically and tagged in the Ledger. This page is for the rest: cash, banks without alerts, anything the phone did not see. It makes entry fast and shows the effect on balance and plan live. If you add a credit here and the bank message arrives later (same amount, within a day), the message is linked to it, not doubled. See section 4 of the root `README.md`.

## Shell differences

- No nav item is active (all muted, no underline). The `+ Add credit` button stays in the header with `aria-current="page"` and the accent background.
- The aside glyph is a pale `+` (the `credit` icon); `h1` is `Add credit`.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph | pale `+` icon (same size and colour as every page glyph) |
| `h1` | `Add credit` |
| Description (`.opt`) | "Salary, refunds, gifts and cash. Credits in your bank's messages add themselves; use this page for everything else." |
| Ledger-math A (`margin-top: clamp(12px,2.6vh,28px)`) | `balance now` **37,591** / `+ this credit` **{amount}** / **`= new balance {37,591 + amount}`**: `balance now` and `= new balance` are ink (balances), `+ this credit` is green (money in) |
| Ledger-math B (`.opt2`, `margin-top:24px`) | `money to plan 50,000` / `+ added to plan {amount if switch on else 0}` / **`= new plan {50,000 + added}`** (accent) |
| Recent credits (`.opt2`, `margin-top:24px`) | header mono caps `RECENT CREDITS` (border-bottom ink); rows `padding: var(--row-pad) 0; border-bottom:1px solid #E6E6EA`: `OCT 01 Salary +50,000`, `SEP 01 Salary +50,000`, `AUG 01 Salary +50,000` (amounts green) |

### Main: form (`rise` entrance; flex column)
1. **Amount** (`flex:none`)
   - Label (for the input) mono caps 11px muted `HOW MUCH CAME IN`.
   - Row: `display:flex; align-items:baseline; gap:6px; border-bottom:1px solid ink; margin-top:4px`. `₹` span `calc(var(--fs-display) * 0.4)`, 300, muted. Input (text **green**, because it is money in): `flex:1; border:0; background:transparent; font-size: var(--fs-display); weight 300; tracking −0.06em; line-height 1.1`, placeholder `0` in `#CFCFD6`, `inputmode="numeric"`, `autocomplete="off"`.
   - **Quick add** (`.opt2`): text links `+ 1,000`, `+ 5,000`, `+ 10,000`, `+ 50,000` (mono 13px, accent underline, min-height 36px, gap 22px). Each **adds** to the current amount.
2. **Two columns** (`display:flex; flex-wrap:wrap; gap: clamp(14px,2.4vh,26px) clamp(32px,4vw,64px); margin-top: clamp(10px,2.2vh,24px)`):
   - **Where it came from** (`flex:3 1 340px`): mono caps `WHERE IT CAME FROM · A TAG` with ink bottom rule; **tag chips** (`margin-top: clamp(8px,1.6vh,14px)`, gap 8px): `#salary` (default selected), `#freelance`, `#refund`, `#gift`, `#interest`. Chip (shared): 34px high, padding `0 14px`, mono 13px, 1px border `#CFCFD6`; selected = ink fill, white text, ink border; hover border ink. Below: an underline input `new tag, e.g. #bonus` (max-width 340px; the shared underline input, 18px/300) + text link `add`.
   - **When** (`flex:2 1 280px`): mono caps `WHEN`; segmented control `Today | Yesterday | Pick a date` (32px, shared); beneath it mono 13px `#3B3B42` the resolved date (`Oct 18, 2026` / `Oct 17, 2026` / chosen date); when "Pick a date" is active show a native `<input type="date">` (max `2026-10-18`, default `2026-10-15`).
3. **Note** (`margin-top: clamp(10px,2.2vh,24px)`): label mono caps `NOTE · OPTIONAL`; underline input (shared: height `clamp(34px,5vh,42px)`, 18px/300), placeholder `October salary`.
4. **Plan switch** (`.opt`; `margin-top: clamp(10px,2vh,20px)`; `padding:12px 0`; top and bottom rules `#E6E6EA`; flex space-between): title "Add it to this month's plan" (500) + help "Raises your "money to plan" so you can give the new money a job." (13px muted) + switch 36×20 (shared, default on).
5. **Actions** (`margin-top: clamp(12px,2.6vh,28px)`; flex wrap gap 12px 24px; centred): primary button `Add credit` (44px, `padding:0 28px`, disabled until amount > 0), text link `Cancel` (muted, → Now), and (`.opt`) mono 11px muted footnote "bank credit alerts add themselves; this page is for cash and everything else".

### Main: success state (`pop` entrance; vertically centred; `max-width:760px`)
- 44×44 accent square containing a white 22px check icon.
- Mono caps `CREDIT ADDED` (11px muted), `margin-top: clamp(12px,2.4vh,24px)`.
- Amount in the hero style: `₹` small muted + saved amount at `var(--fs-display)`, 300, tracking −0.06em.
- Sentence (`var(--fs-lead)`, `#3B3B42`): "landed in **#salary** on {date}. Your balance is now **₹{new}**." Tag ink with a 2px accent underline; balance accent/500.
- Actions: primary link `Back to Now` (44px) and text button `Add another` (accent underline).

## State

| State | Type | Default |
|---|---|---|
| `amount` | digit string, max 9 chars | `''` |
| `tag` | string | `'salary'` |
| `tags` | string[] | `['salary','freelance','refund','gift','interest']` |
| `draft` | string | `''` (new-tag input) |
| `date` | `'today' \| 'yesterday' \| 'pick'` | `'today'` |
| `dateStr` | `YYYY-MM-DD` | `'2026-10-15'` |
| `note` | string | `''` |
| `planOn` | boolean | `true` |
| `done` | boolean | `false` |
| `saved` | number | `0` (amount captured at submit) |
| `savedTag` | string | `''` |

## Behaviour (exact)

```ts
value = parseInt(amount || '0', 10) || 0
onAmountChange(raw): amount = raw.replace(/[^0-9]/g, '').slice(0, 9)   // strips commas, letters
display = value ? value.toLocaleString('en-IN') : ''                    // re-grouped every keystroke
quick(n): amount = String(value + n).slice(0, 9)
addTag(): t = draft.replace(/#/g,'').trim().toLowerCase();
          if (!t) return; tag = t; if (!tags.includes(t)) tags.push(t); draft = ''
newBalance = 37591 + (done ? saved : value)
planAdd    = planOn ? value : 0;   newPlan = 50000 + planAdd
canSubmit  = value > 0
submit():  done = true; saved = value; savedTag = tag
another(): done = false; amount = ''; note = ''; date = 'today'
dateText   = today → 'Oct 18, 2026'; yesterday → 'Oct 17, 2026';
             pick → format dateStr as 'Mon D, YYYY'
```

Examples (verified): typing `5x0,000` → shows `50,000`, new balance `87,591`, new plan `1,00,000`; `+ 1,000` then → `51,000`; adding tag `#Bonus` creates and selects chip `#bonus`; switch off → new plan `50,000`; submit → success shows `₹51,000`, `#bonus`, balance `₹88,591`.

In production, `submit()` should POST a credit `{ amount, tag, date, note, addToPlan }`, then update the balance and (if `addToPlan`) the current month's "money to plan".

## Responsive notes

- Amount font scales by `min(vw, vh)`; on short windows the quick-add chips (`.opt2`) and the plan switch + footnote (`.opt`) disappear so the form still fits.
- Body area scrolls if it still cannot fit; the header stays.
- Columns wrap under each other on narrow widths.

## Acceptance checklist

- [ ] Empty amount → `Add credit` disabled (30% opacity); typing enables it.
- [ ] Amount re-formats with Indian grouping on every keystroke; letters are ignored.
- [ ] Aside arithmetic updates live: 37,591 + amount; plan 50,000 + amount only when the switch is on.
- [ ] Selecting a tag inverts it to ink; new tags appear as chips and become selected.
- [ ] "Pick a date" reveals the date input; `Today`/`Yesterday` update the date text.
- [ ] Success view shows the saved amount, tag, date and new balance; `Add another` returns to an empty form.
- [ ] The header keeps the Add credit button, shown as the current page (accent background); no nav item is underlined.
