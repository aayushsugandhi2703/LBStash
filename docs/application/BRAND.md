# Brand and colours

The logo, the name, the icons and the colours. Files are in `frontend/public/brand`. Colour values live in `frontend/src/app/globals.css` (CSS variables at the top).

## Name

Spell it **LBStash**: capital L, B and S, the rest lowercase. Never `LBSTASH`, `lbstash` or `Lbstash`. Two colours: **LB** in ink, **Stash** in the accent green. Font: Geist, weight 600, letter spacing `-0.03em`. On a dark background outside the app, or on the green, use all white.

## Film

The 46 s film on the About page (built in `promo/`) uses the same colours and the same logo, wordmark rules and mono labels. It is drawn with the macOS system font as a stand-in, because Geist is not installed on the build machine; with Geist installed, `promo/build.sh` takes `LB_FONT_SANS` and `LB_FONT_MONO` (see `promo/README.md`).

## Logo

A lowercase **b** made of a stem and a coin, white on a square tile.

| File | Use |
|---|---|
| `mark.svg` | the mark alone, on `#00875A`: tab icon, app icon, avatars |
| `logo.svg` | mark and name side by side, for light backgrounds: README, emails |
| `LogoMark`, `Logo` in `frontend/src/brand/logo.tsx` | inside the app. They follow `--accent`, so they follow the theme |

- Smallest size: 16 px for the mark, 96 px wide with the name.
- Clear space: half the mark's width on every side.
- Never stretch it, rotate it, round the tile, recolour the white shapes, or write the name in capitals.

## Icons

Each icon has two files: an **image** (`<name>.svg`, fine line, for docs and cards) and a **favicon** (`<name>.favicon.svg`, bolder, clear at 16 px). Safari needs a PNG, so pages also have `<name>.favicon.png` (180 × 180).

**Tab icons.** Every page has its own, so open tabs are easy to tell apart. `pageIcon()` in `frontend/src/brand/brand.ts` maps a path to its file. To add a page: add its three files in `public/brand/pages/` and one line in `PAGE_ICONS`.

**Services** (`public/brand/services/`), one ink colour `#2F3A35`, only the symbol changes:

| | Service | Symbol |
|---|---|---|
| <img src="../../frontend/public/brand/services/gateway.svg" width="28" alt=""> | `gateway` | an archway |
| <img src="../../frontend/public/brand/services/auth.svg" width="28" alt=""> | `auth` | a shield with a tick |
| <img src="../../frontend/public/brand/services/transactions.svg" width="28" alt=""> | `transactions` | list lines |
| <img src="../../frontend/public/brand/services/planning.svg" width="28" alt=""> | `planning` | four blocks |
| <img src="../../frontend/public/brand/services/recurring.svg" width="28" alt=""> | `recurring` | a circling arrow |
| <img src="../../frontend/public/brand/services/reports.svg" width="28" alt=""> | `reports` | a rising line |
| <img src="../../frontend/public/brand/services/telegram.svg" width="28" alt=""> | `telegram` | a paper plane |
| <img src="../../frontend/public/brand/services/ingest.svg" width="28" alt=""> | `ingest` | an arrow into a tray |

**Pages** (`public/brand/pages/`): `now`, `money`, `budget`, `forecast`, `account`, `security`, `devices`, `setup` in the accent green; `sign-in`, `create-account`, `reset`, `secure` in graphite `#2B3236`, so they read as a separate area.

## Colours

Change a variable in `globals.css`, then rebuild the web image (`docker compose build web && docker compose up -d web`).

| Group | Variable: value | Used for |
|---|---|---|
| Green | `--accent` `#00875A` | money in, links, active tab |
| | `--accent-light` `#00A06B`, `--accent-dark` `#005C3D` | bar ends |
| | `--accent-pale` `#C9EEDD`, `--accent-ribbon` `#D8F3E7` | big icons, flow ribbon |
| Text | `--ink` `#0E0E10`, `--text-2` `#3B3B42`, `--muted` `#6B6B73` | text, secondary text, captions |
| Surfaces | `--surface` `#FFFFFF`, `--rule` `#E6E6EA`, `--track` `#EDEDF1` | page, lines, empty bars |
| | `--disabled` `#CFCFD6`, `--hover-row` `#FAFAFB`, `--hover-index` `#F6F6F8` | disabled, hovers |
| Warning | `--warn` `#E9A800`, text `#8A6200` | close to the limit, "Needs a look" |
| Danger | `--danger` `#C93030` | errors, over the limit |

The Budget page (Plan tab) colours its categories with a grey ramp (`--ramp-0` to `--ramp-8`, `RAMP` in `frontend/src/features/plan.ts`). The Google Pay hand-off page (`frontend/src/app/pay/route.ts`) has its own small dark palette.

### Dark mode

Chosen in **Account > Appearance** (System, Light or Dark) and saved in the browser (`localStorage`, key `lbstash-mode`). A script in `<head>` sets `data-mode` on `<html>` before the first paint, so the page never flashes white. `:root[data-mode="dark"]` in `globals.css` gives each variable its dark value.

Keep both modes working:

- Text on a filled colour uses `--on-ink`, `--on-accent` or `--on-danger`, never `#fff`.
- A card, menu or input above the page uses `--raised`, never `#fff`.
- Never write a literal grey or white. Use a variable, or add one with a dark value. Only QR codes (they must stay white to scan) and the switch knob are exceptions.
