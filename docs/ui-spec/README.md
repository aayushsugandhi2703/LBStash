# Budget Tracker · UI Spec

A page-by-page build spec for the **Ledger** budget-tracker interface: a minimal, light, editorial web app with one accent colour, an icon nav and an Account menu instead of a sidebar, and a month ruler that shows where you are in the month on every signed-in page.

Follow these files and you can rebuild every screen **exactly**, in any stack (React/Next.js, Vue, Svelte, plain HTML+CSS).

> Live design (Claude artifacts, private to the owner), 16 boards each
> - Emerald: https://claude.ai/artifact/TvRcbS8jWC82q5xB1WV2r3
> - Caribbean blue: https://claude.ai/artifact/8bie2RSFM8PVaJEB2XihGF

## Status

**All 16 screens are designed and specified.** Specs, reference files and the live designs are in sync as of the last update. Nothing has been built or tested in a real browser yet; the designs were checked as markup and by running their logic, not by eye.

| Area | # | Page | Route (suggested) | Spec | Reference |
|---|---|---|---|---|---|
| Design system | 00 | Tokens, shell, components, states, copy rules | n/a | [`00-design-system`](00-design-system/SKILL.md) | n/a |
| App | 01 | Now | `/` | [`01-now`](01-now/SKILL.md) | `reference/Main.dc.html` |
| App | 02 | Ledger (with check panel, Unaccounted, split) | `/ledger` | [`02-ledger`](02-ledger/SKILL.md) | `reference/Transactions.dc.html` |
| App | 03 | Plan | `/plan` | [`03-plan`](03-plan/SKILL.md) | `reference/Plan.dc.html` |
| App | 04 | Limits | `/limits` | [`04-limits`](04-limits/SKILL.md) | `reference/Budgets.dc.html` |
| App | 05 | Repeats | `/repeats` | [`05-repeats`](05-repeats/SKILL.md) | `reference/Recurring.dc.html` |
| App | 06 | Trends | `/trends` | [`06-trends`](06-trends/SKILL.md) | `reference/Reports.dc.html` |
| App | 07 | Add credit | `/credit` | [`07-add-credit`](07-add-credit/SKILL.md) | `reference/Credit.dc.html` |
| App | 08 | Needs a look (child of Ledger) | `/ledger/unread` | [`08-needs-a-look`](08-needs-a-look/SKILL.md) | `reference/NeedsLook.dc.html` |
| Account | 09 | Profile | `/account` | [`09-profile`](09-profile/SKILL.md) | `reference/Account.dc.html` |
| Account | 10 | Security | `/account/security` | [`10-security`](10-security/SKILL.md) | `reference/SecuritySettings.dc.html` |
| Account | 11 | Devices and Telegram | `/account/devices` | [`11-devices`](11-devices/SKILL.md) | `reference/Devices.dc.html` |
| Auth | 12 | Sign in (password, then second step) | `/sign-in` | [`12-sign-in`](12-sign-in/SKILL.md) | `reference/SignIn.dc.html` |
| Auth | 13 | Create account | `/create-account` | [`13-create-account`](13-create-account/SKILL.md) | `reference/CreateAccount.dc.html` |
| Auth | 14 | Secure your account | `/secure` | [`14-secure`](14-secure/SKILL.md) | `reference/Secure.dc.html` |
| Auth | 15 | Reset password | `/reset` | [`15-reset`](15-reset/SKILL.md) | `reference/Reset.dc.html` |
| Onboarding | 16 | Setup guide | `/setup` | [`16-setup-guide`](16-setup-guide/SKILL.md) | `reference/Setup.dc.html` |

The numbers in the folder names are only file ids and build order. **The interface itself shows no sequence numbers.** The routes for 12 to 15 are suggestions: the design files only name the pages.

## Build order

1. **`00-design-system`** first: tokens, the signed-in shell (icon nav, Account menu, ruler), the sign-in shell, and every shared component. Every page depends on it.
2. **Auth, then the shell:** 13 → 14 → 12 → 15 (phase "Foundation and sign-in" in the root README).
3. **Ledger core:** 07 Add credit, 02 Ledger (read side), 01 Now.
4. **Plan, Repeats, Limits, Trends:** 03, 05, 04, 06.
5. **Capture and Telegram:** 16 Setup guide, 08 Needs a look, the Ledger check panel and Unaccounted row, 11 Devices and Telegram.
6. **Account safety:** 09 Profile, 10 Security.

The root `README.md` section 19 maps these onto the 12 delivery phases and says which design each phase needs.

## How to use

1. Read **`00-design-system/SKILL.md` first.**
2. Build a page from its spec. Each spec has: purpose, shell differences, layout tree with sizes, copy, data, state, calculations, interactions, responsive behaviour and an acceptance checklist.
3. Use **`reference/*.dc.html`** as the numeric source of truth when a spec and your result disagree. They are the exact design files. They use a small templating dialect (`{{ }}`, `<sc-for>`, `<sc-if>`) and a `renderVals()` function, so they will not run on their own, but every inline style and formula in them is authoritative. `reference/` holds all 16 files.
4. Where a spec says "the file does X, build Y", the spec wins (it records a deliberate fix).

## Using these as Claude Code skills (optional)

Every `SKILL.md` starts with `name` + `description` frontmatter. To make them invokable in Claude Code, copy each folder into `.claude/skills/`:

```bash
for d in docs/ui-spec/[01]*/; do cp -R "$d" ".claude/skills/budget-ui-$(basename "$d" | cut -d- -f2-)"; done
```

Then ask: *"Build the Security page using the budget-ui-security skill."*

## What the design contains that you might not expect

- **One signed-in header** on 12 screens: six icon links (Now, Ledger, Plan, Limits, Repeats, Trends; Ledger carries a count badge), a `+ Add credit` button, an **Account menu** (Profile and preferences, Security, Devices and Telegram, Setup guide, Needs a look, Sign out) and a month ruler. **No logo and no sequence numbers.** The four sign-in screens keep a wordmark-only header.
- **Page glyph:** the big pale mark at the top of each aside is the page's own icon, not a number.
- **Inline confirmation:** anything that could lock the user out or move data (change email, export, delete, rotate or cancel the token, new recovery codes, change password) opens a grey well under its row asking for the authenticator code. No pop-ups anywhere.
- **Bars shade from a deeper tone to the normal tone** of their own colour (the only gradients in the design; narrow on purpose).
- **Colour meaning:** balances are ink, money in is green, money out is ink, limits go green → yellow (at the alert level, default 80%) → red (exceeded). A debit is never green and a credit is never black.
- **No bank details outside the web app:** Telegram and other channels say "Money out · 6:42 pm". The Setup guide and Devices page explain Reveal.
- **Month in progress is never shown as final:** hatched pace blocks, "pace" labels and "so far".
- **States:** every list and chart has a defined empty, loading and error state (`00-design-system` §10), and copy and number formatting rules are in §11.

## Prototype stand-ins (the designs fake these; the real app must not)

The reference files are interactive mock-ups. These behaviours exist only so the design can be clicked through:

| Where | Stand-in | Real behaviour |
|---|---|---|
| Sign in | Any well-formed email plus any non-empty password passes step 1; the code `000000` is the only "miss"; passkey and recovery code have no failure path | Server verifies everything; 3 wrong codes pause sign-in for 15 minutes (README 15.2) |
| Create account | Strength meter was too generous for short passwords (fixed: under 12 characters is always `weak`) | Server also checks a breached-password list |
| Secure | QR, secret key and recovery codes are placeholders; any 6 digits confirm; copy buttons only flash their label; "download .txt" does nothing; the header's "step 2 of 3" never moves | Generated per account, codes shown once, real clipboard and file download |
| Reset | Only a regex and a length check; Continue is never disabled; the done link goes to the Secure flow | Server checks the recovery code; a signed-out user must not reach Secure without signing in |
| Setup guide | `/start 482915` and the 4:52 timer are static; copy links only flash; the digest and after-tag choices do not change the preview | Per-user pairing code with a real 5-minute expiry; real clipboard |
| Ledger check panel | Accepts any amount (try 37,411 for a ₹180 gap); booking is instant | Grace period (default 6 hours) before a gap is booked, and a late matching message replaces it |
| Profile, Security, Devices | Every "authenticator code" accepts any 6 digits; export, delete, token and passkey actions only change local state | Server re-verifies the code per action and writes the audit log |
| Needs a look | Adding a message only changes local state | Creates a ledger entry and teaches the parser; deleting removes the encrypted text |

## Principles the design never breaks

- **One accent, used for meaning.** Emerald `#00875A` (or Caribbean `#007F95`) marks money coming in and "within limit"; it doubles as the interface highlight (active nav, links, today). Yellow `#E9A800` and red `#C93030` mean limit state; the only other yellow is the "in progress or paused" status square, always paired with words.
- **Ink, white, hairlines.** No cards, no shadows, no rounded corners (radius 0, even on buttons, chips and switches). Structure comes from 1px rules and whitespace. The one gradient is the narrow same-hue shade on bars.
- **Two typefaces.** Geist for reading, Geist Mono for labels and numbers in lists.
- **The page never scrolls.** Header is fixed, content fits the window, anything longer scrolls inside its own panel. Sizes scale with window width and height; optional text hides on short screens.
- **One definition per component.** Rows, progress bars, plots, tooltips, legends, segmented controls, steppers, switches, inputs, buttons (primary, ghost, bad), chips, links, wells and status lines are specified once in `00-design-system` §4. A page never restyles them.
- **Same height for the same control everywhere:** segmented 32px, stepper 30px, switch 36×20, small and ghost button 36px, large button 44px, input `clamp(34px,5vh,42px)`.
- **Plain words.** "Needs a tag", "Needs a look", "kept", "heading for". Money is `₹` with Indian grouping; negatives use a true minus.

## Recent changes

- All 16 screens now have specs; account area, auth, setup and Needs a look added.
- Header: icon nav, Account menu, no logo, no numerals (page glyphs instead).
- Trends rebuilt as one sentence, one chart and one list.
- Balances are ink; bars use a narrow same-hue gradient.
- Design system gained ghost and bad buttons, settings row, inline confirmation well, code input, status line, strip links, Account area layout, states and copy rules.
- Fixes from the spec pass: Setup now tells the user to add the Dictionary action first, points "redo a step" at Devices and Telegram, opens the real @BotFather link, shows the opening balance in ink; short passwords can no longer rate `okay` on Create account.
