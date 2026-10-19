---
name: budget-ui-security
description: Build the Security page of the Ledger budget tracker (Account area): password change, authenticator, passkeys, recovery codes, signed-in browsers with sign out, and the append-only activity log, all with inline authenticator-code confirmation. Matches reference/SecuritySettings.dc.html.
---

# 10 · Security

Reference: `reference/SecuritySettings.dc.html` · Route `/account/security` · Requires `00-design-system` (*Account area*, *Inline confirmation*).

**Purpose.** Show and change how the user signs in, where they are signed in, and what has happened on the account. Two-step sign-in is always on and cannot be turned off.

## Shell differences

Same as Profile: signed-in header, no nav item lit, Account button outlined with an accent avatar, shared Account-area aside.

## Layout

### Aside
Glyph `security` (shield with a tick) · `h1` **Security** · description "How you sign in, where you are signed in, and what happened lately. Changes here ask for your code." · sibling list (Security current) · summary `.opt2`: `two-step on` / `passkeys 2` / `browsers 3` / **`= sign-in strong`** (accent).

### Main
Header: label `SECURITY`, title "Sign-in and sessions", lead "Two-step sign-in is always on and cannot be turned off. Passkeys are the quickest way in; the authenticator app and recovery codes are your backups."

**1. SIGN-IN METHODS** (settings rows; each action is a ghost button, never a link)
| Row | Copy | Action and well |
|---|---|---|
| **Password** | "Changed 12 days ago. Changing it signs every other browser out." | `Change password` / `Cancel`. Well: `CURRENT PASSWORD`, `NEW PASSWORD · AT LEAST 12 CHARACTERS` with a mono counter (`7 of 12 characters`, then `12 characters · long enough`), `AUTHENTICATOR CODE`; primary `Save password`, enabled when current is non-empty, new ≥ 12 and the code is 6 digits. After saving: green line "Password changed. Other browsers were signed out." and the browser list drops to this browser only |
| **Authenticator app** | "On since Oct 02. Asked for at every password sign-in." | `Replace` / `Cancel`. Well: "You will scan a new QR code, as when you first set up. The old app stops working the moment you confirm the new one." + primary link `Scan a new code` → Secure |
| **Passkeys** | "Face ID, Touch ID or a security key. A passkey never leaves the device that made it." | `Add a passkey`. Below, one row per passkey (indented 16px, hover `--hover-row`): name, mono meta (`added Oct 02 · used today 6:42 pm`), and a red text link `Remove` that becomes `Tap again to remove` on first tap (second tap removes). Empty: "no passkeys · you sign in with password and authenticator code" |
| **Recovery codes** | "{n} of 10 unused. Each works once, if you lose your authenticator." | `Make new codes` / `Cancel`. Well: "Making new codes cancels all the old ones, used or not." + code input + `Make new codes`. Then a well titled `SHOWN ONCE · SAVE THEM SOMEWHERE SAFE` with 10 codes in a mono grid (`repeat(auto-fit, minmax(140px,1fr))`), and the count becomes 10 of 10 |

**2. WHERE YOU ARE SIGNED IN.** One row per session: name 14/500, mono meta (`Bengaluru · active now`); the current one carries a small accent badge `this browser` (mono 11px, white on accent) and has no sign-out; others have a text link `Sign out`. Below: ghost **bad** button `Sign out all other browsers` (disabled when none) and the mono note "the Telegram bot session is on Devices".

**3. ACTIVITY** (`role="table"`). Rows: mono 11px time (132px), event (14px, flexible), mono 11px place (right). Footer: "This log is append-only. Nobody, including you, can edit or remove an entry."

## Sample data

| Sessions | Meta |
|---|---|
| Chrome on Mac (this browser) | Bengaluru · active now |
| Safari on iPhone | Bengaluru · 2 hours ago |
| Chrome on Windows | Mumbai · Oct 11 |

| Passkeys | Meta |
|---|---|
| iPhone · Face ID | added Oct 02 · used today 6:42 pm |
| MacBook · Touch ID | added Oct 05 · used Oct 16 |

Activity (newest first): OCT 18 6:42 PM signed in with a passkey, Chrome on Mac · OCT 18 6:31 PM Telegram bot signed in, bot · OCT 16 9:10 AM signed in with an authenticator code, Chrome on Windows · OCT 11 8:55 PM **two wrong authenticator codes, then a right one** (text `#8A6200`), Chrome on Windows · OCT 05 7:20 PM passkey added: MacBook · OCT 04 6:02 PM Telegram linked · OCT 02 5:48 PM ingest token created for the iPhone · OCT 02 5:31 PM account created.

Recovery codes shown (sample): `k4tq-9m2x r7wd-3hna z8pb-6cve m2fj-5ysu c9ga-1txk h6ne-8dqp y3vu-4bwr a5ls-7jzm p1xc-2geh w8dt-9fko`.

## State

`pwOpen`, `pwCur`, `pwNew`, `pwCode`, `pwDone`, `totpOpen`, `passkeys[]`, `removing` (id awaiting the second tap), `codesAsk`, `codesCode`, `codesShown`, `codesLeft`, `sessions[]`. Only code inputs are digit-filtered (max 6). Wells are independent here (several can be open).

## Acceptance checklist

- [ ] Save password stays disabled until all three fields are valid; saving leaves one browser in the list.
- [ ] First tap on Remove changes the label; second tap removes; removing both shows the empty line.
- [ ] Add a passkey appends a "This device · passkey" row.
- [ ] New recovery codes show 10 codes once and the line reads 10 of 10.
- [ ] `Sign out` removes that session; `Sign out all other browsers` leaves only the current one and disables itself.
- [ ] The activity log has 8 rows and the 11 Oct row is dark yellow.
