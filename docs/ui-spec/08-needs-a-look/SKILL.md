---
name: budget-ui-needs-a-look
description: Build the "Needs a look" queue of the Ledger budget tracker: bank messages the parser could not read, each shown as its original text with direction, amount and payee fields so the user can add it to the ledger or delete it. Child page of Ledger. Matches reference/NeedsLook.dc.html.
---

# 08 · Needs a look

Reference: `reference/NeedsLook.dc.html` · Route `/ledger/unread` · Requires `00-design-system`.

**Purpose.** The phone caught a bank message but the wording was new or the parser found no usable amount. The message waits here, encrypted, for at most 30 days. The user tells the app what it was (it joins the ledger like any captured payment) or deletes it. Backend rules: README sections 4.6 and 4.7 ("weak parse", unparsed messages, "Keeping the parser current").

## Shell differences

- Signed-in header. **Ledger is the lit nav item** (this page is a child of Ledger); the page is also reachable from the Account menu (hint = live count) and from the `LOOK` links on Now and Ledger.
- Aside glyph: the `look` icon (question mark in a circle).

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | `look` icon / `Needs a look` |
| Description (`.opt`) | "Bank messages the app could not read. Tell it what they were, or throw them away." |
| Ledger-math | `waiting 2` / `− sorted today {n}` / **`= still to look at {n}`** (value accent). `waiting` is fixed at 2 in the sample; the other two are live |
| Note (`.opt2`) | 13px muted, top rule `#E6E6EA`, `margin-top:24px`: "Messages wait here encrypted and are deleted after 30 days. Anything that looks like a one-time code is never kept." |
| Link | mono 13px text link with accent underline: `← back to the ledger` |

### Main
Standard main header (see design system, *Account-area main*): label `UNREAD MESSAGES`, title "Messages we could not read" (`--fs-fig-lg`, 300), lead "The phone caught these, but the wording was new. Add one as a payment and it joins the ledger like any other; the next message in that style may then read on its own."

One block per message (`rise`, `padding: var(--row-pad) 0 clamp(12px,2vh,18px)`, bottom rule `#E6E6EA`). Two modes.

**Open**
1. Mono caps 11px muted line: `{when} · {reason}`, the reason in dark yellow `#8A6200` (e.g. `OCT 17 · 9:12 PM · amount found, direction unclear`).
2. The **original message** in a grey well (`#F6F6F8`, `padding:12px 14px`, mono 13px, line-height 1.6, `#3B3B42`, `overflow-wrap:anywhere`). Digits that identify an account are already masked as `••••` by the server.
3. Controls row (`flex-wrap`, gap `12px 24px`, `margin-top:12px`): **segmented control** `Money out | Money in` (label `THIS WAS`); **amount** underline input (140px, mono, label `AMOUNT ₹`, digits only, max 9); **payee** underline input (`flex:1 1 200px`, label `PAID TO · OPTIONAL`).
4. Actions row (`margin-top:14px`): primary button `Add to the ledger` (36px, disabled until amount > 0) and a red text link `Not a payment, delete it`.

**Done** (replaces the open mode): a 9px accent square and one sentence, with `tag it in the ledger →` (only after an add) and `Undo` (text links) on the right:
- added: `Added to the ledger: −₹1,250 · Amazon Pay · needs a tag` (direction sign, amount with Indian grouping, payee if typed, `· needs a tag` for money out);
- deleted: `Deleted. The message is gone for good.`

When every message is done, a centred muted line: "All sorted. Messages the app cannot read will wait here." Footer caption mono 11px muted: "A message is kept for 30 days, then deleted. Deleting one here removes it for good."

## Sample data

| id | When | Reason | Text | Prefill |
|---|---|---|---|---|
| u1 | OCT 17 · 9:12 PM | amount found, direction unclear | `Txn of INR 1,250.00 on card ending •••• at AMAZON PAY INDIA, 17-Oct. Avl bal INR ••••••. Not you? Call the number on the back of your card.` | out, `1250`, `Amazon Pay` |
| u2 | OCT 14 · 8:03 AM | no amount found | `Your a/c ending •••• has been updated. Please check the app for details.` | out, empty, empty |

## State and behaviour

- State per message: `{ dir: 'out'|'in', amount: string, name: string, done: '' | 'added' | 'dismissed' }`.
- `Add` is disabled while amount is 0. `Undo` returns to the open mode with the typed values kept.
- Counts: still to look at = messages with `done === ''`; sorted today = 2 − that. The Account menu hint and the `LOOK` links show the same live count in the real app.
- Adding creates a ledger entry with `source = captured`, `status = confirmed`, no category (so it appears under "Needs a tag" in the Ledger).

## Responsive notes

- Controls wrap; the well text wraps anywhere. The main scroller scrolls if several messages are open.

## Acceptance checklist

- [ ] Two messages open on load; "still to look at" reads 2.
- [ ] Message 1 is prefilled out / 1250 / Amazon Pay; message 2's Add button is disabled until an amount is typed.
- [ ] Adding message 1 shows `Added to the ledger: −₹1,250 · Amazon Pay · needs a tag`, count drops to 1.
- [ ] Deleting message 2 shows the deleted line, count 0, and the "All sorted" line appears.
- [ ] `Undo` restores the open form.
- [ ] Ledger is the lit nav item; the Account menu row for this page has the accent left border.
