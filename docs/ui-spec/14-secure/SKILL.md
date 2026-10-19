---
name: budget-ui-secure
description: Build the "Secure your account" page of the Ledger budget tracker (sign-in header): a three-part setup flow with a parts indicator in the margin, authenticator app (example QR, secret key, 6-digit code), required passkey, and recovery codes with an "I have saved these" confirmation that unlocks the finish link. Matches reference/Secure.dc.html.
---

# 14 · Secure your account

Reference: `reference/Secure.dc.html` · Route `/secure` · Requires `00-design-system`. Reached after account creation (header reads "step 2 of 3 · account setup"); also reached from the Reset password done state.

**Purpose.** Require an authenticator app, passkey, and acknowledged recovery codes before the user sees any financial data. Existing users who sign in without a passkey are sent to the passkey step and remain setup-limited until enrollment succeeds.

## Shell differences

- **Sign-in header, not the signed-in header.** Left: the `ledger` wordmark (`--fs-brand`, 600, link to the sign-in page, `padding:14px 0`). Right: mono `--fs-label` muted text `step 2 of 3 · account setup` (static, it does not change with the part). Row has the 1px ink bottom rule. No nav, no Add credit, no Account menu, no month ruler; a spacer `clamp(20px,3vh,28px)` sits under the rule where the ruler would be. Signed-in pages do not carry the wordmark; this page does.
- Aside glyph is the padlock (`M7 11V8a5 5 0 0 1 10 0v3 M5 11h14v10H5Z`), pale as every page glyph. Body area, aside and main use the standard shell sizes.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | padlock / `Secure your account` |
| Description (`.opt`) | "A password alone is not enough for financial data. Three short parts, about two minutes." |
| Block header | mono caps `--fs-label` muted `THREE PARTS`, `margin-top:clamp(12px,2.6vh,24px)`, `padding-bottom:7px`, ink bottom rule |
| Parts indicator | three rows, built like the shared index list but not clickable: `Authenticator app`, `Passkey`, `Recovery codes` |

Each indicator row: flex, space-between, baseline; padding and 3px left border exactly as the index list (`margin-left:-3px`), `--fs-body`, bottom rule `#E6E6EA`. Right value is mono `--fs-s`.

| Row state | Left border | Label | Right text |
|---|---|---|---|
| done (`part` past it) | transparent | 400 `#3B3B42` | `done` in `--accent` |
| now (current part) | 3px `--accent` | 600 ink | `now` muted |
| next | transparent | 400 `#3B3B42` | `next` muted |

### Main (each part enters with `rise`)

**Part 1 · authenticator app** (column, gap `clamp(12px,2.4vh,22px)`)
1. Mono caps label `PART 1 OF 3 · AUTHENTICATOR APP`.
2. Row (wrap, `align-items:flex-start`, gap `clamp(16px,3vh,28px) clamp(24px,3vw,48px)`):
   - QR block (`flex:none`): `role="img"` `aria-label="Example QR code for your authenticator app"`, 21x21 CSS grid, square `clamp(132px,22vh,176px)`, 1px ink border, `padding:8px`, white. Cells are ink or white. Caption under it (mono `--fs-label` muted, `margin-top:8px`): `example code, yours is unique`. Cell rule: in the three 8x8 corner zones (top-left, top-right, bottom-left) a finder pattern (ring on rows/cols 0 and 6, 3x3 centre block at 2-4, row/col 7 empty); elsewhere cell is on when `(r*31 + c*17 + r*c) % 7 < 3`. It is a fixed placeholder, not a real QR.
   - Text column (`flex:1 1 320px; max-width:520px`): title `--fs-title` 500 "Scan it with an authenticator app"; help `--fs-s` muted, line-height 1.55: "Use any authenticator app (Apple Passwords, 1Password, Google Authenticator). Cannot scan? Type this key instead."
   - Secret row (`margin-top:14px`, space-between, bottom rule `#CFCFD6`, `padding-bottom:8px`): mono `--fs-h2` 300 tracking `.06em` `ABCD EFGH IJKL MNOP` and the copy text link.
   - Code well (`margin-top:clamp(12px,2.4vh,22px)`): label mono caps `THEN TYPE THE 6-DIGIT CODE IT SHOWS` (for `#code`) and the cell input below.
3. Primary button `Confirm and continue` (44px), disabled until the code is 6 digits.

**Part 2 · passkey** (`max-width:640px`)
1. Mono caps `PART 2 OF 3 · REQUIRED PASSKEY` (existing users see `REQUIRED · PASSKEY`).
2. Headline (`--fs-fig-lg` 300, tracking −0.035em, line-height 1.15): "Create a passkey to secure your account." Existing users see "Create a passkey to finish signing in."
3. Body `--fs-s` muted, `max-width:520px`: "A passkey lives on this device and cannot be phished. You can still use the authenticator app or a recovery code if the device is lost."
4. When added: a status row (top and bottom rules `#E6E6EA`, `padding:var(--row-pad) 0`, gap 14px): 20px accent square with a white 12px check, title `--fs-title` 500 "Passkey added", sub `--fs-s` muted "This iPhone · today".
5. Actions (wrap, gap 12px 24px): not added = primary `Add a passkey` and the note "A passkey is required to continue"; added = primary `Continue` only. `Back` is shown only during first-time account setup. Text buttons are `--fs-body`, `#6B6B73`, min-height 44px, hover accent.

**Part 3 · recovery codes**
1. Mono caps `PART 3 OF 3 · RECOVERY CODES`.
2. Headline (`--fs-fig-lg` 300, `max-width:640px`): "Keep these 8 codes somewhere safe. This is the only time you see them."
3. Codes grid: 2 columns, `max-width:520px`, ink top rule. Each cell mono `--fs-h2` 300 tracking `.04em`, `padding:var(--row-pad) 0`, bottom rule `#E6E6EA`. Sample codes in order: `k7m2-9qpa`, `x4tn-b83d`, `m9c5-2wzr`, `h3vf-7ke6`, `q8ya-4ndj`, `t2ub-6rxs`, `p5ge-1mhc`, `w6dj-8vlt`.
4. Two mono `--fs-s` text links (ink, accent underline, min-height 36px, gap 24px): copy-all link and `download .txt`.
5. Note, mono `--fs-label` muted, line-height 1.6, `max-width:520px`: "Each code works once. They are the only way back in if you lose your phone and authenticator."
6. Confirmation row (gap 12px): 20px square checkbox button (`role="checkbox"`, `aria-checked`, `aria-label="I have saved these codes somewhere safe"`), 1px ink border; unchecked white, checked ink fill with a white 12px check. Label `--fs-body` "I have saved these somewhere safe".
7. Actions: `Finish and open the setup guide` (44px) and muted `Back`. Until the box is ticked the button is a disabled `<button>` (opacity .3); once ticked it is an `<a>` to the Setup guide (`/setup`).

## Copy buttons and flash

| Control | Rest label | Flash label |
|---|---|---|
| Secret key (mono `--fs-s`, min-height 32px) | `copy` | `copied` |
| Recovery codes | `copy all` | `copied all` |

Click sets the flash flag for **1600 ms**, then clears it; each button flashes independently. The reference only flips the label; in production also write to the clipboard (secret as `ABCDEFGHIJKLMNOP` or as shown; codes one per line).

## State

| State | Default | Notes |
|---|---|---|
| `part` | `1` | 1, 2 or 3; drives main, indicator |
| `code` | `''` | digits only, max 6 |
| `passkey` | `false` | set by `Add a passkey` |
| `saved` | `false` | toggled by the checkbox |
| `copiedSecret`, `copiedCodes` | `false` | flash flags |

## Behaviour (exact)

```ts
onCode(v):    code = v.replace(/[^0-9]/g,'').slice(0,6)      // letters and spaces dropped
cantConfirm = code.length !== 6                              // any 6 digits enables it
confirmApp(): part = 2        addPasskey(): passkey = true
Continue (part 2, only after passkey enrollment): part = 3        Back: part-1 (first-time setup only)
toggleSaved(): saved = !saved             // finish link live only when saved
```
- Code input: `type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000"`, full width, height `clamp(48px,7vh,64px)`, 1px ink bottom rule (darker than the shared `#CFCFD6` input), mono `--fs-fig-lg` 300, **letter-spacing .4em** so the six digits read as cells (one continuous field, not six boxes). Placeholder `#CFCFD6`.
- Going Back keeps `code`, `passkey` and `saved`; indicator is recomputed from `part` only, so a visited part after the current one reads `next` again.
- Existing users who have completed setup but have no passkey see only the required passkey step; after enrollment, return to the originally requested page.
- The flow ends at the **setup guide** (`/setup`) via the enabled finish link. Production: verify the TOTP server-side before leaving Part 1, register the passkey with WebAuthn, store the hashed recovery codes.

## Responsive notes

- Aside description hides below 800px height (`.opt`); QR size, headline and code height scale with `vh`.
- QR block and text column wrap under each other on narrow widths; codes grid stays 2 columns.

## Acceptance checklist

- [ ] Header shows `ledger` left and `step 2 of 3 · account setup` right; no nav, ruler or Account menu.
- [ ] Indicator shows `now` with a 3px accent border on the current part, `done` in accent for earlier parts, `next` otherwise.
- [ ] `Confirm and continue` stays disabled until exactly six digits are typed; letters are ignored.
- [ ] Copy links flip to `copied` / `copied all` for about 1.6 s and return.
- [ ] Part 2: `Add a passkey` swaps in the "Passkey added" row and a `Continue` button; `Skip for now` goes to Part 3 without adding.
- [ ] Part 3 shows eight codes in two columns; the finish button is disabled until the checkbox is ticked, then links to the setup guide.
- [ ] `Back` works from Parts 2 and 3; no Back on Part 1.
- [ ] Focus ring, radius 0, no shadows, reduced-motion respected.
