---
name: budget-ui-setup-guide
description: Build the "Setup guide" page of the Ledger budget tracker: a four-step guided setup (connect iPhone Shortcut, connect Telegram, Telegram privacy choices, first month numbers) plus an all-done summary, with a step index and steps-done arithmetic in the aside, copy fields that flash "copied", checkbox rows, live Telegram message preview and Back / Continue / Finish footer. Matches reference/Setup.dc.html.
---

# 16 · Setup guide

Reference: `reference/Setup.dc.html` · Route `/setup` · Requires `00-design-system`. Opened from Account menu row `Setup guide` (hint `about 15 min`) and after sign-up.

**Purpose.** Walk a new user, once, through the two capture channels (iPhone Shortcut and a private Telegram bot), the one privacy decision Telegram needs, and the first-month numbers, so bank messages flow into the Ledger by themselves. The wording of this page mirrors `README.md` 4.5 (Shortcut steps), 4.10 (test first), 5.5 (sign-in) and 5.8 (what Telegram can see); do not paraphrase the strings marked **exact** below.

## Shell differences

- **No nav item is lit** (all muted, none underlined); `+ Add credit` is the normal dark button (not current). Ledger keeps badge `1`; ruler is day 18.
- In the Account menu the `Setup guide` row is the current page (3px accent left border). `Needs a look` hint is the literal `2 messages` in the file.
- Aside glyph is the `tick over a line` icon (path `M5 12l4 4l10-10 M4 20h16`), shared glyph size and colour.

## Layout

### Aside
| Element | Spec |
|---|---|
| `h1` | `Setup guide` |
| Description (`.opt`) | "Four steps so your bank messages flow into the ledger on their own. About 15 minutes, once." |
| Block header | mono caps 11px muted `FOUR STEPS`, `margin-top:clamp(12px,2.6vh,24px)`, `padding-bottom:7px`, `border-bottom:1px solid ink` |
| Step list | the shared **Index list** in a `role="group"` labelled "Setup steps". Four buttons, label left, state word right (mono 13px) |
| Arithmetic (`.opt2`, `margin-top:24px`) | ledger-math block: `account secured` **yes** (accent, constant) / `steps done` **{n} of 4** / final row **`= still to do {4 − n}`** (ink in the file, not accent) |

Step list rows (label → state word):

| # | Label | State word shown |
|---|---|---|
| 1 | Connect your iPhone | `done` when `token && test`; else `now` if it is the open step; else `todo` |
| 2 | Connect Telegram | `done` when `botSaved && linked && signed`; else `now` / `todo` |
| 3 | Telegram privacy | `done` when `step > 3`; else `now` / `todo` |
| 4 | Your first month | `done` when `step > 4` (that is, on the all-done view); else `now` / `todo` |

- `done` is checked **first**, so a finished step you are standing on reads `done`, not `now`. State word `done` is `--accent`, `now` and `todo` are muted. The active row (the open step) still gets the 3px accent border and 600/ink label whatever its word.
- Clicking any row jumps straight to that step (no gating). On the all-done view (`step = 5`) no row is active.
- `n` = number of true flags in `[step1, step2, step3, step4]`. Steps 3 and 4 count as done merely by having been moved past, so jumping back to step 4 from the all-done view drops `n` by one.
- The account-secured line is always `yes`; it is not one of the four steps.

### Main
Flex column: **step header** (`flex:none`), then a **content scroller** (`flex:1 1 0; min-height:0; overflow-y:auto; margin-top:clamp(10px,2vh,18px); border-top:1px solid ink`), then the **footer** (steps 1–4 only).

**Step header**
| Element | Spec |
|---|---|
| Label | mono caps 11px muted: `STEP {n} OF 4`; on the final view `ALL DONE` |
| Title | `h2`, `--fs-fig-lg` 300, tracking −0.035em, line-height 1.15, `margin-top:6px`: the step label above (step 3 and 4 titles are the same words as the index); final view `You are set up.` |
| Lead | 13px muted, line-height 1.55, `max-width:680px`, `margin-top:8px` (strings below) |

Leads, **exact**:
1. "Your iPhone forwards each bank debit and credit message to your server. You set it up once in the Shortcuts app; nothing to install."
2. "Telegram is where each payment arrives with category buttons, so you can tag it whenever you like. It takes a bot of your own, one link step and a sign-in."
3. "Telegram keeps whatever its messages contain, so yours carry no bank details at all. Choose the one optional exception and how long the bot session lasts."
4. "So the plan, the limits and the balance start from real numbers."
Final: "Here is what is connected. You can redo any step later from Devices and Telegram in the Account menu."

Every step body enters with the shared `rise` animation (re-plays when the step changes).

## Shared pieces on this page

**Step row** (steps 1 and 2): flex, gap 18px, `padding:var(--row-pad) 0`, bottom rule `#E6E6EA`. Number `01`..`06` mono 11px muted, 24px wide, `padding-top:3px`; body `flex:1; min-width:0` with title `--fs-title`/500, then a 13px muted explanation (`margin-top:2px`, line-height 1.55), then the control block (`margin-top:10px`); checkbox at the far right when present.

**Checkbox** (row control, step 1 only): `<button role="checkbox" aria-checked aria-label="Mark step {n} done">`, 20×20, `1px solid ink`, `margin-top:2px`; off = white, on = ink fill with a white 12px tick (stroke 3). The user can tick or untick rows 01 to 05 freely. Row 06's box is a **non-interactive `span`** (`aria-hidden`, default cursor) that mirrors `test`. These checkboxes are a personal to-do aid: **they do not feed** the step state word or `steps done` (only `token` and `test` do).

**Copy link**: text link `copy` (mono 13px, ink, accent underline offset 5px, min-height 32px on the token and command, hover to accent). For keyword chips it is mono 11px muted with no underline. **Flash**: clicking sets `copied[key] = true` and the label reads `copied`; after **1600 ms** it returns to `copy`. Keys are independent: `token`, `kw1`, `kw2`, `url`, `header`, `body`, `cmd`. The file only flips the label; production must also write the value to the clipboard (token, keyword, URL, the full `Authorization: Bearer <token>` header with the real token, the three body lines, `/start 482915`).

**Status line**: 9px square then mono 13px text. Waiting = `#E9A800` square with the shared `wait` pulse (`.35 → 1`, 1.1s, off under reduced motion); done = `--accent` square, no pulse. The yellow square is also used (static) as the bullet of the two warning notes in step 1; this page uses yellow for notices, an exception to the "yellow = limit state" rule in `00-design-system`.

**Preview link**: `preview: simulate …` (mono 11px muted, underlined). It stands in for the real server event (message arrived, Telegram linked, signed in) and is what flips the flags in the prototype. In production it is replaced by live polling and removed.

**Segmented control** and **Switch** are the shared components (32px segments, 36×20 switch); **Underline input** is shared (label mono caps 11px, 18px/300 text).

## Step 1 · Connect your iPhone

Six rows. `token` and `test` both true marks the step done.

| # | Title (exact) | Body and control |
|---|---|---|
| 01 | Create your ingest token | "A secret that lets your phone send messages and nothing else. It cannot read your data, and you can cancel it any time." Before: small button `Create token`. After: pale `#F6F6F8` box (`padding:10px 14px`, flex space-between) with mono `ledg_live_8f3a2c91d7e4b605` and copy link; caption mono 11px muted below: "shown once, copy it now · lose it and you simply make a new one". Checkbox. |
| 02 | Open Shortcuts and start an automation | "On your iPhone open the Shortcuts app, tap the Automation tab, tap + to make a new personal automation, then pick Message." Path box mono 13px: `Shortcuts › Automation tab › + › Message`. Checkbox. |
| 03 | Set the trigger: match your bank's words | "The Sender box only lists people in your contacts, so a bank's sender name (like AX-HDFCBK) cannot be picked there. Leave it empty. Tap Choose next to the box that filters on the message text (Apple's guide calls it Message Contains) and type a phrase that your bank's alerts always contain. Check a real alert first." Keyword chips `debited`, `credited` (each with its own copy link) plus a chip for the optional field below once typed. Underline input (max-width 360px) label "Your bank's name as it appears in its alerts (optional)", placeholder `HDFC Bank`. Warning note (yellow square): "Two ways, pick one. debited and credited (one automation each) keep OTPs on your phone, but would also match another sender's debit text. Your bank's name catches only that bank's alerts in a single automation, but the bank's OTP texts that mention it also reach your server, which drops them unread (it answers 202 and stores nothing)." Checkbox. |
| 04 | Add the action: Get Contents of URL | "Search for Get Contents of URL and add it, then tap Show More. Set Method to POST, add the header below, set Request Body to JSON and use Add new field for each line of the body (type Text); to insert a value such as Shortcut Input, tap the value box and pick it from the variable bar above the keyboard. For the nonce, add a Random Number action above this one (any range, for example 10000000 to 99999999) and use its result. That is the whole shortcut: two actions." Then the **request-fields table** (top rule `#E6E6EA`, rows `padding:8px 0`, label mono caps 11px muted 84px wide, value mono 13px, copy link right). Checkbox. |
| 05 | Run it immediately | "On the same screen pick **Run Immediately**, not **Run After Confirmation** (older iOS calls that one Ask Before Running). If a **Notify When Run** switch is shown, turn it off; newer iOS may always show a banner for this option, which is fine. Open the shortcut's settings (the ⓘ button), go to Privacy and turn on **Allow Running When Locked** if it is listed. Run the shortcut once yourself and, if iPhone asks to allow sending data to your server, choose Always Allow. Then tap Done and repeat for the second word." (bold = 500 ink). Warning note: "iPhone may run it late while locked. That is fine: each payment is saved at the time written in the bank message, and a balance check later catches anything that never arrives." Checkbox. |
| 06 | Send a test | "**Lock your phone first**, then ask someone to text you `Rs 1.00 debited test` (mono), or just wait for your next bank alert. This page will notice and show how long it took." Status: waiting = pulsing yellow + "waiting for your first message…" + `preview: simulate a message`; received = green + "received · −₹1.00 · test message · arrived 14 s after it was sent". Read-only box mirrors `test`. |

Request fields (row 04), copyable independently:

| Label | Value |
|---|---|
| URL | `https://your-server/ingest/message` (ellipsis; copy key `url`) |
| METHOD | `POST` (no copy) |
| HEADER | key `Authorization`, value `Bearer ledg_live_••••••••` (shown as `Authorization = Bearer ledg_live_••••••••`, masked on screen; copy key `header` copies only `Bearer <token>`, the value box) |
| BODY | three mono lines: `text = Shortcut Input` / `receivedAt = Current Date (Date Format: ISO 8601)` / `nonce = Random Number + Current Date` (copy key `body`) |

Rules this step must keep (**exact meaning**): the shortcut is exactly **two actions** (Random Number, then Get Contents of URL, whose JSON Request Body takes the three fields directly; there is no separate Dictionary action); trigger is a text phrase typed into the message-text filter (never Sender, which lists contacts only; never an empty filter); Run Immediately with Notify off; **a late run is normal** because the payment is booked at the time written in the message and the balance check catches the rest. Terms follow Apple's Shortcuts guide: trigger `Message` (Sender lists contacts only; the text filter is Apple's `Message Contains`, entered via `Choose`); run options `Run Immediately` / `Run After Confirmation` (formerly `Ask Before Running`); `Allow Running When Locked` under the shortcut's Privacy settings; `Get Contents of URL` with `Show More`, `Method`, `Headers`, `Request Body` (`JSON`, `Form`, `File`).

## Step 2 · Connect Telegram

Four rows, no checkboxes. Done when `botSaved && linked && signed`.

| # | Title (exact) | Body and control |
|---|---|---|
| 01 | Create your own bot | "In Telegram open `@BotFather`, send `/newbot`, pick a name and a username ending in `bot`. BotFather replies with a token." (code words mono). Link `open @BotFather in Telegram ↗` (mono 13px, accent underline, min-height 36px; opens `https://t.me/BotFather` in a new tab, `rel="noopener"`). |
| 02 | Give the server the token | "It is stored encrypted on your server and never shown again. Anyone with the token could talk as your bot, so do not paste it anywhere else." Not saved: label `BOT TOKEN`, password input (`type=password`, `autocomplete=off`, placeholder `123456789:AAH…`, mono 18px/300) + button `Save token`, **disabled while the typed token is under 20 characters**. Saved: green status "saved and encrypted · •••••••••:AAH••••••••" + muted link `replace`. |
| 03 | Link your Telegram account | "Open your new bot and send this message. The code works once and expires in 5 minutes. After this, only your Telegram id can use the bot." Pale box with `/start 482915` (mono 18px/300, tracking .04em), muted `expires in 4:52` and copy link (key `cmd`). Status: waiting "waiting for your message to the bot…" + `preview: simulate linking`; linked "linked · @aayush · id ••4821 · private chat only". |
| 04 | Sign in to the bot | "Send `/signin`, then the 6-digit code from your authenticator app. The bot deletes your code message. You stay signed in until you send `/signout`. While signed out the bot sends nothing and payments wait for you." Status: waiting text is `link your account first` until linked, then `waiting for /signin and your code…`; `preview: simulate sign-in` appears only once linked. Signed: "signed in · stays until you send /signout". |

Notes: the `/start` code and the `expires in 4:52` text are static in the file (no countdown); production counts down and issues a fresh code on expiry. `replace` clears `botSaved`, `linked` and `signed`, returning the whole step to waiting. Bot token is never echoed back; the input is cleared on save.

## Step 3 · Telegram privacy

Two columns that wrap (`gap:clamp(16px,3vh,28px) clamp(28px,4vw,56px)`).

**Left** (`flex:1 1 340px; max-width:520px`):
| Block | Spec |
|---|---|
| Header | mono caps muted `WHAT TELEGRAM NEVER GETS` with ink rule |
| Statement (14px, `#3B3B42`, **exact**) | "No amount, no payee, no balance, no account number, no bank name, no UPI ID, no original message. Each message only says that money went out or came in, and when." |
| Reveal row | title `Show a Reveal button` (500) + help (**exact**) "Tap it to see the amount and payee for 30 seconds. While visible, those details pass through Telegram. Off means Telegram never sees any bank detail." + shared switch (`aria-label` same as title). **Default on.** |
| `ALSO SIGN ME OUT OF THE BOT AFTER` | segmented `7 days · 30 days · 90 days` (default 30), `role="group"` "Idle days". Note 13px muted: "You stay signed in until you send /signout. This is only a safety net for when you stop using the bot." |
| `DAILY REMINDER OF UNTAGGED PAYMENTS` | segmented `Off · Daily, 9 pm · Twice a day` (default Daily, 9 pm), group "Digest" |
| `AFTER YOU TAG A PAYMENT` | segmented `Keep it · One line · Delete it` (default One line), group "After tagging" |

Section labels are mono caps 11px muted, `margin-top:clamp(12px,2.4vh,22px)`; segmented controls `margin-top:8px`, `width:fit-content`.

**Right** (`flex:1 1 280px; max-width:380px`): header `HOW IT WILL LOOK IN TELEGRAM`; pale box (`#F6F6F8`, `padding:16px 18px`, `margin-top:12px`):
- Line 1 mono 18px/300: `Money out · 6:42 pm` (constant).
- Line 2 mono 13px muted: Reveal on → `tap Reveal to see the amount for 30 seconds`; off → `no amount, no payee, no balance`.
- Button preview (wrap, gap 6px, `margin-top:14px`, each a 30px mono 13px `1px solid #CFCFD6` white box, not clickable): `Food`, `Travel`, `Fun`, `Bills`, `＋ New tag`, then `Reveal` **only when Reveal is on**, then `Later`.
- Caption mono 11px muted (**exact**): "Your category names (Food, Rent…) do show on the buttons. Nothing about the bank does."

The digest and after-tag choices do not change the preview in the file. Reveal changes line 2 and the Reveal button; idle days feed only the final summary.

## Step 4 · Your first month

Single column, `max-width:560px`, gap `clamp(12px,2.4vh,22px)`.

| Field | Spec |
|---|---|
| Opening balance | mono caps label `BALANCE OF YOUR BANK ACCOUNT RIGHT NOW (OPENING BALANCE)`; row with muted `₹` and numeric input (18px/300, ink, because it is a balance), placeholder `0`. Help (**exact**): "Use the one bank account these messages come from. Cash goes in later as credits. The app carries this forward every month, and now and then compares it with your bank: any payment that never reached it is booked as Unaccounted for you to tag or split." |
| Money to plan this month | label `MONEY TO PLAN THIS MONTH`; same input in ink, **prefilled `50,000`**. Help: "You split this across categories on the Plan page. It can differ from what you earn." |
| Alert level | label `WARN ME WHEN A LIMIT IS`; segmented `70% · 80% · 90%` (default 80), group "Alert level" |
| Ledger-math (`max-width:360px`) | `opening balance ₹{opening}` / `to plan this month ₹{plan}` / `= alerts at {level}% used` |

Both inputs: digits only (`replace(/[^0-9]/g,'')`, max 9 chars), applied on commit (change/blur), shown with Indian grouping; an empty or `0` opening shows the placeholder. The arithmetic block shows `₹0` for empty values. The balance is a position, so the typed opening balance is ink (see `00-design-system` colour meaning).

## All-done view (`step = 5`)

Header `ALL DONE` / `You are set up.`; **footer is hidden**.
- Summary list (`max-width:620px`, top rule `#E6E6EA`): rows `padding:var(--row-pad) 0`, bottom rule; leading 10px square (ok = accent fill, not ok = white with 1px `#CFCFD6`), label 14/500, mono 13px value (ink if ok, muted if not):

| Label | Value |
|---|---|
| Account secured | `password + second step` (always ok) |
| iPhone connected | `first message received` if step 1 done, else `not finished` (not ok) |
| Telegram linked and signed in | `@aayush · id ••4821`, else `not finished` |
| Telegram shows | `No details, Reveal on` or `No details at all` |
| Bot session | `until /signout, or {idle} idle days` |
| Opening balance (bank account) | `₹{opening}` |
| Money to plan this month | `₹{plan}` |

- Sentence (`--fs-lead`, `#3B3B42`, `margin-top:clamp(14px,2.6vh,24px)`, **exact**): "The next time your bank messages you, it shows up here and in Telegram within seconds. Tag it once per new payee."
- Actions: large button `Open Now` (to `/`) and muted text link `See the Ledger` (to `/ledger`), 44px high.

## State

| State | Type | Default | Flipped by |
|---|---|---|---|
| `step` | 1..5 | `1` | index row (sets it), footer Continue / Skip (`min(5, step+1)`), Back (`max(1, step−1)`) |
| `token` | bool | `false` | `Create token` (also ticks `done.a`); never unset |
| `done.a..e` | bools | all `false` | their checkboxes (free toggle); `a` also by Create token |
| `test` | bool | `false` | `preview: simulate a message` (live: first captured message arrives) |
| `botToken` | string | `''` | token input; cleared on save |
| `botSaved` | bool | `false` | `Save token`; cleared by `replace` |
| `linked` | bool | `false` | `preview: simulate linking`; cleared by `replace` |
| `signed` | bool | `false` | `preview: simulate sign-in` (only offered when linked); cleared by `replace` |
| `reveal` | bool | `true` | Reveal switch |
| `idle` | 7 / 30 / 90 | `30` | idle segmented |
| `digest` | `off` / `daily` / `twice` | `daily` | digest segmented |
| `after` | `keep` / `edit` / `delete` | `edit` | after-tag segmented |
| `opening` | digit string | `'0'` | opening input |
| `plan` | digit string | `'50000'` | plan input |
| `level` | 70 / 80 / 90 | `80` | alert segmented |
| `copied` | map key to bool | `{}` | any copy link (1600 ms flash) |

Derived: `s1 = token && test`, `s2 = botSaved && linked && signed`, `s3 = step > 3`, `s4 = step > 4`; `steps done = count(s1..s4)`; `still to do = 4 − steps done`.

## Footer (steps 1 to 4)

Flex wrap, gap `8px 24px`, `padding-top:clamp(8px,1.6vh,14px)`, `border-top:1px solid #E6E6EA`, `margin-top:clamp(6px,1.2vh,10px)`, `flex:none`.

| Control | Spec |
|---|---|
| Primary (large button) | label `Continue` on steps 1 to 3, **`Finish`** on step 4; moves to `step + 1` (step 4 goes to the all-done view) |
| `Back` | muted text link, 44px; goes to `step − 1`, does nothing on step 1 (it is still shown, not disabled) |
| `Skip for now` | muted text link, 44px; identical action to Continue (no required field blocks any step) |

## Responsive notes

- The content scroller is the only thing that scrolls inside Main; the footer stays pinned under it.
- Aside description is `.opt` (hidden below 800px height); the steps-done block is `.opt2` (hidden below 700px). The step index itself always stays.
- Step 3 columns wrap under each other on narrow widths; request-field values ellipsise on one line (BODY wraps); the token and command boxes wrap their copy link below.

## Acceptance checklist

- [ ] No nav item is lit; the `Setup guide` Account-menu row has the accent left border.
- [ ] Aside lists the four steps; the open one has the 3px accent border and bold label; clicking any row opens that step.
- [ ] Initially `steps done 0 of 4`, `= still to do 4`; all states read `now` (step 1) or `todo`.
- [ ] `Create token` reveals `ledg_live_8f3a2c91d7e4b605` with the "shown once" caption and ticks the first checkbox.
- [ ] Every `copy` link reads `copied` for 1.6 s then `copy`; links flash independently.
- [ ] Step 1 shows the exact two-action wording, the OTP warning, Run Immediately (with Notify When Run off where shown), and the "late is fine" note; row 06's box cannot be clicked.
- [ ] Simulated message shows the green received line; step 1 reads `done` and `steps done` becomes 1 only when token and test are both true.
- [ ] `Save token` is disabled under 20 characters, clears the field and shows the masked saved line; `replace` resets link and sign-in.
- [ ] Sign-in waits on `link your account first` until linked; simulate-sign-in button appears only after linking; step 2 reads `done` when saved, linked and signed.
- [ ] Step 3 privacy statement, Reveal wording (30 seconds, "passes through Telegram") and idle-days note match the strings above; Reveal on by default.
- [ ] Turning Reveal off removes the `Reveal` preview button and switches preview line 2 to `no amount, no payee, no balance`.
- [ ] Step 4 opening balance and plan accept digits only, group in Indian format, plan starts at 50,000; the arithmetic block updates and `= alerts at 80% used` follows the segmented level.
- [ ] Footer label is `Continue` on steps 1 to 3 and `Finish` on 4; Back does nothing on step 1; `Skip for now` equals Continue.
- [ ] All-done view hides the footer, lists seven summary rows with filled or hollow squares, and offers `Open Now` and `See the Ledger`.
- [ ] No step is gated: skipping everything still reaches the all-done view with `not finished` on the unfinished rows.
