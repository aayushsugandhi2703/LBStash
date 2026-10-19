---
name: budget-ui-create-account
description: Build the "Create account" page of the Ledger budget tracker: email, password with show/hide, a live strength meter (red, yellow, green same-hue gradients), a four-item password rules list, confirm-password match, and a success state that leads to the Secure your account page. Uses the sign-in header (wordmark, no nav, no ruler). Matches reference/CreateAccount.dc.html.
---

# 13 · Create account

Reference: `reference/CreateAccount.dc.html` · Route `/create-account` · Requires `00-design-system`.

**Purpose.** Create the single account (email and password) before anything else. The account is not usable until a second step exists, so success hands straight over to the Secure your account page.

## Shell differences

- **Sign-in header, not the signed-in header.** Row 1 only, `border-bottom:1px solid --ink`: left, wordmark `ledger` (`--fs-brand`, 600, −0.04em) linking to `/sign-in`, `padding:14px 0`; right, a text link in mono `--fs-label` muted, `padding:12px 0`, hover `--accent`: `already have the account? sign in` (to `/sign-in`). Below it an empty spacer `height:clamp(20px,3vh,28px)`. **No nav, `+ Add credit`, Account menu or month ruler.** Signed-in pages never show the wordmark; this page does.
- Body scroller padding is `clamp(6px,1.4vh,12px) clamp(20px,3.5vw,64px) clamp(16px,3vh,32px)`; everything else is the shared shell.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph | pale person-plus (`M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8Z M4 20c0-4 4-6 8-6 M18 14v6 M15 17h6`) |
| `h1` | `Create your account` (same in the form and success states) |
| Description (`.opt`) | "This app has one account: yours. Next you add a second step, then connect your phone." |
| Block header | mono caps `--fs-label` muted `SETUP, IN ORDER`, `margin-top:clamp(12px,2.6vh,24px)`, `padding-bottom:7px`, `border-bottom:1px solid --ink` |
| Index list (display only, not links) | `Account` **now** (active: 3px accent left border, 600), `Secure it` **next**, `Setup guide` **then** (inactive, `--text-2`). It never advances on this page, even after success |

### Main, form (`rise`, `max-width:560px`, column gap `clamp(12px,2.2vh,22px)`)
1. **Email**: label `EMAIL`; underline input, `type="email"`, `autocomplete="username"`, placeholder `you@example.com`.
2. **Password**: label row (`PASSWORD` left, `show` / `hide` text-button right, mono `--fs-s`, ink, accent underline, `min-height:32px`); underline input, `autocomplete="new-password"`, placeholder `at least 12 characters`. Under it (`margin-top:10px`, flex, gap 12px) the **strength meter**: track `flex:1`, height `--bar-s` (4px), `--track`; fill `height:100%`; right of it a mono `--fs-label` muted word, `min-width:44px`, right-aligned.
3. **Confirm password**: label `CONFIRM PASSWORD`; underline input, `autocomplete="new-password"`, placeholder `type it once more`. It uses the same show/hide state as the password (one toggle for both).
4. **Rules list** (column, rows `padding:5px 0`, gap 12px, `--fs-s` `--text-2`): a 10×10 square then the text. Unmet = white with `1px solid #CFCFD6`; met = solid `--accent` fill. Squares are `aria-hidden`, so keep the words.
5. **Actions** (flex wrap, gap `12px 24px`): large button `Create account` (disabled until valid) and, `.opt`, mono `--fs-label` muted "stored as an Argon2id hash, never as text".

### Rules and meter

| Rule text | Met when |
|---|---|
| At least 12 characters | `password.length >= 12` |
| Not a commonly used password | password non-empty and lower-cased password is **not** one of `password1234`, `123456789012`, `qwertyuiop12`, `iloveyou1234`, `passwordpassword` |
| Does not contain your email name | password non-empty and NOT (email name, the part before `@` lower-cased, has 3+ characters and appears in the lower-cased password) |
| Both passwords match | confirm non-empty and equal to password |

**Score:** if the password is shorter than 12 characters the score is 1 (`weak`) as soon as anything is typed and 0 when empty; otherwise it is 1 + (rule 2) + (rule 3) + (`password.length >= 16`), range 1 to 4. The match rule is **not** part of the score. A short password therefore can never read `okay` or `strong`.

| Score | Label | Fill gradient | Width |
|---|---|---|---|
| 0 or 1 | `weak` | red `linear-gradient(90deg,#8E1F1F,#DA4444)` | 0% / 25% |
| 2 | `okay` | yellow `linear-gradient(90deg,#B88400,#F2B705)` | 50% |
| 3 or 4 | `strong` | green `linear-gradient(90deg,#005C3D,#00A06B)` | 75% / 100% |

Width = `score / 4` of the track. Empty password: width 0 and **no label**. Fill transitions `width .35s cubic-bezier(.2,.8,.2,1)` and `background .2s`; none with reduced motion. These are the shared narrow same-hue bar gradients; the red/yellow/green here are strength colours, not limit state.

### Main, success (`rise`, `max-width:640px`, gap `clamp(12px,2.4vh,22px)`)
44×44 accent square with white 22px check · mono caps `ACCOUNT CREATED` · `--fs-lead` `--text-2` sentence: "Your account **{email}** exists. You cannot sign in properly until a second step is set up, so that comes next." (email ink, 2px accent underline, offset 4px) · one large link `Secure your account` to the Secure your account page (`/secure`, the second-step setup). There is no back link and no skip.

## State

`email`, `password`, `confirm` (all `''`), `showPw` (`false`), `done` (`false`).

## Behaviour (exact)

```ts
validEmail = /^\S+@\S+\.\S+$/.test(email)
canCreate  = validEmail && len && common && emailName && match   // button disabled otherwise
toggleShow: showPw = !showPw        // password and confirm both switch type; label show <-> hide
create:     done = true             // the file only flips the view
```

- Rules, meter and button recompute from state on every render, so build them on **per-keystroke** input events (the file wires `onChange`).
- Production: `create()` should POST `{ email, password }`, hash with Argon2id server-side, then show the success view. Only one account may exist, so after it does, `/create-account` should redirect to `/sign-in` (the sign-in page says this link only works before the account exists).

## Responsive notes

- Aside stacks above main on narrow windows. Description and the Argon2id note hide below 800px height (`.opt`). Form is capped at 560px.
- The form is short, but the body scroller scrolls if a very short window cannot fit it.

## Acceptance checklist

- [ ] Header shows `ledger` and `already have the account? sign in`; no nav, ruler or Account menu.
- [ ] Empty password: meter empty, no label, all four rule squares hollow, `Create account` disabled at 30% opacity.
- [ ] 12+ characters not on the common list and not containing the email name: rules 1 to 3 turn green and the meter reads `strong` in the green gradient; 16+ fills it fully.
- [ ] A password equal to `password1234` fails rule 2; one containing a 3+ character email name fails rule 3 (meter drops to `okay` or `weak` accordingly).
- [ ] `weak` uses the red gradient, `okay` yellow, `strong` green, and the fill width moves in quarters.
- [ ] Confirm must equal password for the fourth rule; any mismatch keeps the button disabled.
- [ ] `show` reveals both password fields at once.
- [ ] A valid email (`name@host.tld`) is required; an invalid one keeps the button disabled.
- [ ] Create shows the check, `ACCOUNT CREATED`, the entered email and a `Secure your account` button leading to the Secure page.
- [ ] Aside index still reads Account (now), Secure it (next), Setup guide (then).
