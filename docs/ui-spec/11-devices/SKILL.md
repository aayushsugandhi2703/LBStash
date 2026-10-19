---
name: budget-ui-devices
description: Build the Devices and Telegram page of the Ledger budget tracker (Account area): iPhone capture status, test message, ingest token rotate and cancel, Telegram link and bot session, Reveal, idle days, digest, after-tag, and the tracked bank account with balance-check status. Matches reference/Devices.dc.html.
---

# 11 · Devices and Telegram

Reference: `reference/Devices.dc.html` · Route `/account/devices` · Requires `00-design-system` (*Account area*, *Inline confirmation*, *Switch*, *Segmented control*).

**Purpose.** Everything about where bank messages come in and where prompts go out, in one place, after the Setup guide has done the first-time work. Privacy rules: README sections 4 and 5 (Telegram never carries a bank detail unless the user taps Reveal).

## Shell differences

Signed-in header, no nav item lit, Account button outlined with an accent avatar, shared Account-area aside.

## Layout

### Aside
Glyph `devices` (phone) · `h1` **Devices and Telegram** · description "Where your bank messages come in from, and where your prompts go out." · sibling list (Devices current) · summary `.opt2`: `iphone receiving` / `telegram {signed in | signed out | unlinked}` / `balance matched` / **`= capture working`** (accent).

### Main
Header: label `DEVICES`, title "Capture and the bot", lead "Your phone sends bank messages in. Telegram only asks you to tag them, and never carries a bank detail unless you tap Reveal."

**1. IPHONE CAPTURE**
- **Status row:** 9px square (accent receiving, red when the token is cancelled), title `Receiving` / `Not receiving`, mono 11px line "last message today 6:42 pm · arrived 14 s after it was sent" (or "the token was cancelled, so the phone cannot send"); ghost `Send a test message` (disabled when cancelled). Test: a pulsing yellow square "waiting for the test message…" for ~1.5 s, then a green line "Test message received and read. It was not added to your ledger."
- **Ingest token row:** title, mono 11px `ledg_live_8f3a…b605 · made Oct 02 · last used today 6:42 pm` (masked; `cancelled` or `ledg_live_b21e…8f56` afterwards), ghost `Make a new token` and ghost **bad** `Cancel token`; note below "The token can only send messages in. It cannot read anything."
  - Rotate well: "The old token stops working at once. Until you paste the new one into the Shortcut, no bank message will reach the ledger." + code input + `Make a new token`. Then a well with the new token (mono 13px), `Copy` (flashes `Copied` 1.6 s) and "shown once · paste it into the Shortcut's header action now".
  - Cancel well: "Use this if the phone is lost. Capture stops until you make a new token in the Setup guide." + code input + red ghost `Cancel the token`. Then a red line "Token cancelled. The phone can no longer send messages." with a primary link `Open the Setup guide`.
  - Rotate and cancel wells are mutually exclusive and share one code field state.
- A text link `Run the Setup guide again →`.

**2. TELEGRAM**
- Row: `Linked to your Telegram` + mono `id ••••4821 · linked Oct 04 · only this id can use the bot`; ghost **bad** `Unlink`. Unlinked state: `Not linked` + "the bot will not send or accept anything", a primary link `Open the Setup guide`, and a note "Prompts are paused and nothing is sent to Telegram. Link the bot again from the Setup guide; it takes about a minute." The rows below hide when unlinked.
- **Bot session row:** 9px square (accent signed in, yellow signed out), `Signed in to the bot` / `Signed out of the bot`, line "Since today 6:31 pm. Prompts arrive as they happen." / "Prompts wait here and are released when you send /signin."; ghost `Sign out of the bot` / `Send /signin in Telegram`.
- **Reveal** switch row: "Show a Reveal button. Tap it to see the amount and payee for 30 seconds. While visible, those details pass through Telegram. Off means Telegram never sees any bank detail."
- Three segmented controls, each under a mono caps label: `ALSO SIGN ME OUT OF THE BOT AFTER` (7 / 30 / 90 days; note "You stay signed in until you send /signout. This is only a safety net for when you stop using the bot."), `DAILY REMINDER OF UNTAGGED PAYMENTS` (Off / Daily, 9 pm / Twice a day), `AFTER YOU TAG A PAYMENT` (Keep it / One line / Delete it).

**3. BANK ACCOUNT AND BALANCE**
- `Tracked account`: mono `savings ending 4821 · one account is tracked in this version`; right `₹37,591 in the ledger`.
- `Last balance check`: green square, mono "today 6:50 pm · the bank's number matched the ledger"; ghost link-button `Check now` → Ledger (opens the check panel there).
- `Wait before booking a gap`: "A missing message often turns up late. The app waits this long before it books the difference as an Unaccounted entry." Read-only mono `6 hours`.

## State

`tests` (`idle | waiting | done`), `rotate`, `cancel` (exclusive), `ask`, `token` (`live | new | gone`), `copied`, `linked`, `signed`, `reveal`, `idle` (7|30|90), `digest`, `after`. Unlinking also signs the bot out.

## Acceptance checklist

- [ ] Send a test message shows waiting, then the received line.
- [ ] Rotating shows the new masked token and a one-time copy well; cancelling the token turns the status red and disables the test button.
- [ ] Unlink hides the session, Reveal and the three segmented controls and shows the pause note with the Setup link.
- [ ] Signing out of the bot turns the square yellow, changes the button to `Send /signin in Telegram` and the aside to `signed out`.
- [ ] Reveal switch is 36×20, accent when on; the three segmented controls are 32px high.
- [ ] `Check now` goes to the Ledger.
