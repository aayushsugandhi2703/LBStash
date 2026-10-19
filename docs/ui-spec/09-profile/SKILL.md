---
name: budget-ui-profile
description: Build the Profile page of the Ledger budget tracker (first page of the Account area): name, change email, fixed region note, export everything, delete account (scheduled for 7 days) and sign out of this browser, with inline authenticator-code confirmation. Matches reference/Account.dc.html.
---

# 09 · Profile

Reference: `reference/Account.dc.html` · Route `/account` · Requires `00-design-system` (read *Account area* and *Inline confirmation* there).

**Purpose.** Who the user is to the app, and the two actions that move or destroy data. Anything that could lock the user out or move data asks for the authenticator code inline, never in a pop-up (README section 15, "re-authenticate before changing password or 2FA, creating an export or deleting").

## Shell differences

- Signed-in header; **no nav item lit**, the **Account button** is outlined in ink with an accent avatar (Account area). Aside uses the shared *Account-area aside*.

## Layout

### Aside (Account-area aside)
Glyph `account` (person) · `h1` **Account** · description "Who you are to the app. Sign-in methods are under Security; phones and the bot are under Devices." · sibling list `YOUR ACCOUNT`: **Profile** (current), Security, Devices and Telegram · summary (`.opt2`): `member since oct 02` / `entries kept 18` / `last export never` / **`= your data yours`** (accent).

### Main
Main header (Account-area main): label `PROFILE`, title "Your account", lead "One private account. Anything that could lock you out or move your data asks for your authenticator code first."

Sections use the section header (mono caps with ink rule) and settings rows (`@ROW`: flex, space-between, gap 16px, `padding: var(--row-pad) 0`, rule `#E6E6EA`).

1. **PROFILE**
   - `NAME` underline input (value `Aayush`, `--fs-title`). When it differs from the saved name and is not empty, a row appears: `Save name` (primary 36px), `Undo` (text link), mono muted `unsaved change`. After saving: green square + "Name saved."
   - `EMAIL` `you@example.com` + text link `Change email` (becomes `Cancel`). Opens a grey well: `NEW EMAIL` input, `AUTHENTICATOR CODE` (code input), primary `Send confirmation link` (disabled until the email is valid and the code is 6 digits) and the note "We email a link to the new address. Your sign-in email changes only after you open it." After sending: green line "Link sent to {email}. Nothing changes until you open it."
2. **REGION**: one read-only row "Rupees, India time. Money is shown in ₹ with Indian digit grouping, and days end at midnight in India. Both are fixed in this version." with mono `₹ · IST` on the right.
3. **YOUR DATA**
   - **Export everything** (ghost button `Export`, becomes `Cancel`): "Every entry, tag, plan, limit and repeat in one file. The download link works once and expires in 10 minutes." Opens a well with the code input and `Make the file`. Then a pulsing yellow square and `packing 18 entries…`; then a green square with `ledger-export-2026-10-18.zip · 18 entries · 3 KB` and a primary `Download`.
   - **Delete account** (ghost **bad** button `Delete account`, becomes `Cancel`): "Schedules deletion of your ledger, tokens, passkeys and Telegram link. Sign in within 7 days to cancel. After that it cannot be undone, and backups are cleared on their own schedule." Well: `TYPE DELETE TO CONFIRM` input and the code input; red ghost button `Schedule deletion`, enabled only when the text is exactly `DELETE` and the code has 6 digits. Then a red line "Deletion is scheduled for Oct 25. Signing in before then cancels it." with a `Cancel deletion` link.
4. **THIS BROWSER**: "Sign out. Ends this browser's session. Other browsers and the Telegram bot stay signed in; manage them under Security and Devices." with a ghost link-button `Sign out` to the sign-in page.

## State

`name`, `savedName`, `nameSaved`, `emailEdit`, `newEmail`, `emailCode`, `emailSent`, `ask` (`'' | 'export' | 'delete'`, only one well open at a time), `askCode`, `delText`, `exportState` (`idle | working | ready`), `deleteScheduled`. Code inputs strip non-digits and cap at 6.

## Acceptance checklist

- [ ] Typing a new name shows the save row; Undo restores; Save shows "Name saved."
- [ ] Change email needs a valid address and 6 digits before the button enables; sending shows the green line and closes the well.
- [ ] Export: Cancel closes the well; a code then `Make the file` shows packing, then the file row with `Download`.
- [ ] Delete: the button stays disabled until `DELETE` and 6 digits; scheduling shows the red line with a working `Cancel deletion`.
- [ ] Only one of the two wells is open at a time.
- [ ] The Account button is outlined in ink and the avatar is accent; no nav item is underlined.
