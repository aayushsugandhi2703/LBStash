---
name: budget-ui-reset
description: Build the "Reset password" page of the Ledger budget tracker (sign-in header): a two-step recovery-code reset (email plus one of eight recovery codes, then a new password with a live three-rule checklist), an inline error, and a done state that leads back to sign-in. Matches reference/Reset.dc.html.
---

# 15 · Reset password

Reference: `reference/Reset.dc.html` · Route `/reset` · Requires `00-design-system`. Linked from the sign-in page.

**Purpose.** Let a locked-out user set a new password by proving identity with a one-time recovery code. There is deliberately no "email me a link" path.

## Shell differences

- **Sign-in header, not the signed-in header.** Left: `ledger` wordmark (`--fs-brand`, 600, link to sign-in, `padding:14px 0`). Right: a mono `--fs-label` muted link `back to sign in` (`padding:12px 0`, hover accent) to the sign-in page. 1px ink bottom rule, then a `clamp(20px,3vh,28px)` spacer. No nav, Add credit, Account menu or month ruler. Signed-in pages carry no wordmark; this page does.
- Aside glyph is the reset arrow (`M5 12a7 7 0 1 1 2.1 5 M5 20v-4h4`).

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph / `h1` | reset arrow / `Reset your password` |
| Description (`.opt`) | "There is no "email me a link" here, on purpose. A recovery code proves it is you, and nobody else can intercept it." |
| Ledger-math (`.opt2`, `margin-top:clamp(12px,2.6vh,28px)`, no block header) | `you need` / `1 recovery code`; `other sessions` / `signed out`; final row `= code used up` / `once` (the `once` is `--accent`) |

Rows use the shared ledger-math styling (labels muted, values ink). The block is static on every step.

### Main (each step enters with `rise`, `max-width:560px`, done `640px`)

**Step 1 · recovery code** (gap `clamp(14px,2.6vh,26px)`)
1. Mono caps `STEP 1 OF 2 · PROVE IT IS YOU`.
2. Underline input `EMAIL` (label mono caps for `#email`): `type="email" autocomplete="username"`, placeholder `you@example.com`.
3. Underline input `ONE OF YOUR 8 RECOVERY CODES` (for `#rc`): `type="text" autocomplete="off"`, placeholder `xxxx-xxxx`, **mono** `--fs-h2` 300 (the email field is Geist).
4. Error line (only when set, `role="alert"`): 9x9 `--danger` square, gap 10px, `--fs-s` `--danger` text.
5. Actions: primary `Continue` (44px), and (`.opt`) mono `--fs-label` muted "lost the codes too? you will need to restore from a backup".

Both inputs are the shared underline input: height `clamp(34px,5vh,42px)`, `--fs-h2` 300, bottom rule `#CFCFD6`, placeholder `#CFCFD6`, no box.

**Step 2 · new password** (gap `clamp(12px,2.2vh,22px)`)
1. Mono caps `STEP 2 OF 2 · NEW PASSWORD`.
2. `NEW PASSWORD` field (label left, `show`/`hide` text link right: mono `--fs-s`, ink, accent underline, min-height 32px). Placeholder `at least 12 characters`, `autocomplete="new-password"`.
3. `CONFIRM` field, placeholder `type it once more`, `autocomplete="new-password"`. The show/hide toggle sets the type of **both** fields (`password` / `text`).
4. Rules list (column; each row flex, gap 12px, `padding:5px 0`, `--fs-s` `#3B3B42`, a 10px square marker):

| Rule text | Met when |
|---|---|
| At least 12 characters | `password.length >= 12` |
| Not a commonly used password | password non-empty **and** its lower-case form is not in the common list |
| Both passwords match | confirm non-empty **and** equal to password |

   Marker unmet: white with 1px `#CFCFD6` border. Met: solid `--accent`. Common list (exact, case-insensitive match): `password1234`, `123456789012`, `qwertyuiop12`, `iloveyou1234`, `passwordpassword`.
5. Actions: primary `Set new password` (44px, disabled until all three rules are met) and muted text button `Back` (`--fs-body`, min-height 44px).

**Done**
- 44x44 accent square with a white 22px check, stroke 2.6.
- Mono caps `PASSWORD CHANGED`.
- Sentence (`--fs-lead`, line-height 1.45, `#3B3B42`): "All other sessions were signed out. The recovery code you used is **used up**, so make a fresh set of codes now." `used up` is ink with a 2px accent underline (offset 4px).
- Actions: primary link `Sign in` (44px, to sign-in) and muted text link `Get new recovery codes` (`--fs-body`, min-height 44px, hover accent) to `/secure`.

## State

| State | Default |
|---|---|
| `step` | `'code'` (`'code' \| 'password' \| 'done'`) |
| `email`, `rcode`, `password`, `confirm` | `''` |
| `showPw` | `false` |
| `error` | `''` |

## Behaviour (exact)

```ts
onEmail / onCode:     set value; error = ''          // typing clears the error
onPassword / onConfirm: set value (no error handling)
toPassword():
  if (!/^\S+@\S+\.\S+$/.test(email) || rcode.length < 9)
      error = "That email or recovery code isn't valid."; stay on step 1
  else step = 'password'; error = ''
toCode(): step = 'code'          // values are kept
save():   step = 'done'          // button is disabled unless all rules met
```
- Continue is **always enabled**; the only step-1 feedback is the single error message, shown for both a bad email and a short code (9 characters is the length of `xxxx-xxxx`).
- Production: `toPassword` should only advance after the server accepts the code; `save` must POST email, code and new password, mark the code used, and sign out every other session. Keep the generic error wording so it does not reveal which part was wrong.
- Done leads to **sign-in** (`Sign in`) or to `/secure` (`Get new recovery codes`).

## Responsive notes

- Aside description and the "lost the codes too?" note hide below 800px height; the ledger-math block hides below 700px.
- Aside stacks above main on narrow windows; body scrolls, header stays.

## Acceptance checklist

- [ ] Header shows `ledger` and a `back to sign in` link; no nav, ruler or Account menu.
- [ ] Continue with an invalid email or a code under 9 characters shows the red alert; typing in either field clears it.
- [ ] A valid email and 9+ character code moves to step 2; `Back` returns with values kept.
- [ ] Rule markers turn accent live; `Password1234` is rejected as common, `password1234` too; the button enables only when all three are met.
- [ ] `show`/`hide` flips both password fields and its own label.
- [ ] Done view shows the check, `PASSWORD CHANGED`, the sentence, `Sign in` and `Get new recovery codes`.
- [ ] Focus ring, radius 0, no shadows, reduced-motion respected.
