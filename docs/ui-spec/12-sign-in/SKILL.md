---
name: budget-ui-sign-in
description: Build the "Sign in" page of the Ledger budget tracker: step 1 email and password with show/hide, step 2 second step (authenticator code, passkey or recovery code) with attempts-left and lockout messages, a signed-in state, and a ledger-math summary in the margin. Uses the sign-in header (wordmark, no nav, no ruler). Matches reference/SignIn.dc.html.
---

# 12 · Sign in

Reference: `reference/SignIn.dc.html` · Route `/sign-in` · Requires `00-design-system`.

**Purpose.** Let the one account holder in: password first, then a required second step. One route, one component, three states (`password`, `verify`, `done`). The aside title and description change with the state.

## Shell differences

- **Sign-in header, not the signed-in header.** Row 1 only, `border-bottom:1px solid --ink`: left, the wordmark `ledger` (`--fs-brand`, 600, −0.04em) as a link to `/sign-in`, `padding:14px 0`; right, mono `--fs-label` muted `one private account` (plain text). Below it an empty spacer `height:clamp(20px,3vh,28px)`. **No nav, no `+ Add credit`, no Account menu, no month ruler.** Signed-in pages never show the wordmark; this page does.
- Root, body scroller, aside and main widths, `.opt` / `.opt2` rules, focus ring and `rise` entrance are the shared ones. Body scroller padding is `clamp(6px,1.4vh,12px) clamp(20px,3.5vw,64px) clamp(16px,3vh,32px)`.
- The aside glyph is the pale **arrow** (`M5 12h14 M13 6l6 6l-6 6`) in all three states.

## Layout

### Aside
| Element | Spec |
|---|---|
| Glyph | pale arrow, standard glyph size and colour |
| `h1` | `Sign in` (password) / `Second step` (verify) / `Signed in` (done) |
| Description (`.opt`) | password: "Your ledger is private. Sign in with your password, then a second step." · verify: "Prove it is you with your authenticator app, a passkey or a recovery code." · done: "You are in. Nothing else to do." |
| Ledger-math (`.opt2`, `margin-top:clamp(12px,2.6vh,28px)`) | `two-step` **required** / `session` **15 min, renews** / `your data` **encrypted** / final **`= only you`** with value **`in`** (accent). Same in every state. Labels muted, values ink |

### Main, step 1 · password (`rise`, `max-width:560px`, column gap `clamp(14px,2.6vh,26px)`)
1. Mono caps `--fs-label` muted `STEP 1 OF 2 · PASSWORD`.
2. **Email**: label `EMAIL`; underline input, `type="email"`, `autocomplete="username"`, placeholder `you@example.com`.
3. **Password**: label row (`PASSWORD` left, text-button `show` / `hide` right: mono `--fs-s`, ink, accent underline, `min-height:32px`); underline input, `autocomplete="current-password"`, placeholder `••••••••••••`. `type` is `password`, or `text` while shown.
4. **Error line** (only when an error is set): `role="alert"`, `--fs-s`, `--danger`, a 9px `--danger` square then the message.
5. **Actions** (flex wrap, gap `12px 24px`): large button `Continue` (always enabled) and text link `Reset with a recovery code` (`--fs-body`, muted, min-height 44px) to the Reset page (`/reset`).
6. **Footnote** (`.opt`, mono `--fs-label` muted, `border-top:1px solid --rule`, `padding-top:14px`, line-height 1.6): "New here? " + link `Create the account` (ink, accent underline) to `/create-account` + ". This app has a single account, so this link only works before it exists."

### Main, step 2 · second step (`rise`, same width and gap)
1. Mono caps muted `STEP 2 OF 2 · SECOND STEP FOR {emailShort}`. `emailShort` is the text before `@` (falls back to `you` when email is empty).
2. **Method** segmented control (`role="group"`, `aria-label="Method"`, `align-self:flex-start`, shared 32px buttons): `Authenticator` (default active), `Passkey`, `Recovery code`. Switching clears the error, the code and the recovery code; it does **not** reset attempts.
3. Method body, exactly one of:

| Method | Body |
|---|---|
| Authenticator | label `6-DIGIT CODE FROM YOUR AUTHENTICATOR APP`; input `type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6"`, placeholder `000000`, **ink** bottom rule, height `clamp(48px,7vh,64px)`, Geist Mono `--fs-fig-lg` 300, letter-spacing `.4em` |
| Passkey | no input. Panel with top and bottom `--rule` lines, `padding:clamp(12px,2.4vh,22px) 0`, `max-width:520px`: title `Use your passkey` (`--fs-title`/500) and "Face ID or Touch ID on this device. Nothing to type, and nothing a thief can reuse." (`--fs-s` muted) |
| Recovery code | label `ONE OF YOUR 8 RECOVERY CODES`; underline input (mono, `--fs-h2` 300, `autocomplete="off"`), placeholder `xxxx-xxxx`; note under it (`--fs-s` muted, `margin-top:8px`): "Each code works once. You will be asked to make a fresh set afterwards." |

4. Error line (same component as step 1).
5. **Actions**: large button (`Verify`; `Use passkey` when Passkey is selected; disabled until valid) and text button `Use a different account` (muted, min-height 44px).

### Main, step 3 · done (`rise`, `max-width:640px`, gap `clamp(12px,2.4vh,22px)`)
44×44 accent square with white 22px check (same as Add-credit success) · mono caps `SIGNED IN` · `--fs-lead` `--text-2` sentence "Welcome back, **{emailShort}**. This session lasts 15 minutes and renews while you are active." (name ink, 2px accent underline, offset 4px) · actions: large link `Open Now` (to `/`) and text link `Finish setup guide` (muted, to `/setup`).

## State

`step: 'password' | 'verify' | 'done'` (`'password'`), `email` / `password` / `code` / `recovery` (`''`), `showPw` (`false`), `method: 'app' | 'passkey' | 'recovery'` (`'app'`), `error` (`''`), `attempts` (`3`).

## Behaviour (exact)

```ts
onEmail / onPassword / onRecovery: set value, error = ''
onCode: code = value.replace(/[^0-9]/g,'').slice(0,6); error = ''
toggleShow: showPw = !showPw                      // label flips show <-> hide
continuePw: if (!/^\S+@\S+\.\S+$/.test(email) || password.length < 1)
              error = "That email and password don't match."; stay
            else step = 'verify', error = ''
canVerify = passkey ? true : app ? code.length === 6 : recovery.length >= 9
disabled  = !canVerify || attempts <= 0
verify:    if (method==='app' && code==='000000') {      // the file's stand-in for a wrong code
             attempts -= 1; code = ''
             error = attempts > 0 ? "That code didn't work. N try left." / "N tries left."
                                  : "Too many tries. Wait a minute, then try again."
           } else step = 'done', error = ''
back:      step='password', password='', code='', recovery='', error='', attempts=3  // email is kept
```

- Attempts-left copy: `2 tries left.`, then `1 try left.`; after the third miss the lockout message shows and `Verify` stays disabled until `Use a different account` resets attempts to 3.
- Production: replace the stubs with real calls. Step 1 returns a generic failure message (never say which field was wrong); step 2 counts misses server-side, for every method, and enforces the "wait a minute" lockout. On success, start the 15-minute renewing session.
- Passkey runs the browser's WebAuthn prompt on `Use passkey`; the design only advances to done.

## Responsive notes

- Aside stacks above main on narrow windows. Aside ledger-math hides below 700px height (`.opt2`); description and the "New here?" footnote hide below 800px (`.opt`).
- Form blocks cap at 560px (640px done), so they do not stretch on wide screens.

## Acceptance checklist

- [ ] Header shows only the wordmark `ledger` and `one private account`; no nav, ruler, Add-credit or Account menu.
- [ ] Empty or malformed email, or empty password, then `Continue` shows the red alert "That email and password don't match." and typing clears it.
- [ ] `show` swaps to `hide` and the password becomes visible; toggling back masks it.
- [ ] Valid email plus any password moves to step 2 with `STEP 2 OF 2 · SECOND STEP FOR {name}` and `h1` `Second step`.
- [ ] Authenticator input accepts digits only, max 6; `Verify` is disabled until 6 digits.
- [ ] Passkey shows the panel, no input, and the button reads `Use passkey` and is enabled.
- [ ] Recovery code needs at least 9 characters to enable `Verify`.
- [ ] Three wrong authenticator codes show `2 tries left.`, `1 try left.`, then the lockout message with `Verify` disabled.
- [ ] `Use a different account` returns to step 1, clears the password, keeps the email, resets attempts.
- [ ] Success shows the check, `SIGNED IN`, the welcome sentence and `Open Now` / `Finish setup guide`.
- [ ] `Reset with a recovery code` and `Create the account` link to their pages.
- [ ] Aside summary reads `two-step required / session 15 min, renews / your data encrypted / = only you in`.
