# Colours

Every colour the web app uses. The shared ones are CSS variables at the top of `frontend/src/app/globals.css`; change a variable there and rebuild the web image (`docker compose build web && docker compose up -d web`) to change it everywhere.

**All in one line (light mode; dark values are in the Dark mode section at the end):**
`#00875A #00A06B #005C3D #C9EEDD #D8F3E7 #B3E6CD rgba(0,135,90,.10) #0E0E10 #3B3B42 #6B6B73 #FFFFFF #E6E6EA #EDEDF1 #CFCFD6 #D9D9DF #FAFAFB #F6F6F8 #E9A800 #B88400 #F2B705 #8A6200 #C93030 #8E1F1F #DA4444 #4A4A52 #8E8E98 #B1B1BA #C9C9D2 #C9CDDB #F3F3F6 #9A9AA6`

## Green (accent)

| Hex | Variable | Used for |
|---|---|---|
| `#00875A` | `--accent` | main green: money in, links, active tab, hover on black buttons |
| `#00A06B` | `--accent-light` | bar ends |
| `#005C3D` | `--accent-dark` | bar starts |
| `#C9EEDD` | `--accent-pale` | big page icons, "money not yet given a job" |
| `#D8F3E7` | `--accent-ribbon` | flow-chart ribbon |
| `#B3E6CD` | `--accent-ribbon-hover` | flow-chart ribbon on hover |
| `rgba(0, 135, 90, 0.10)` | `--accent-wash` | soft green background (the main green at 10%) |

The logo mark follows `--accent` in the app (`frontend/src/brand/logo.tsx`); the standalone files in `frontend/public/brand` use `#00875A`. The logo, wordmark and per-service and per-page icons are described in [BRAND.md](BRAND.md).

An alternative blue-green theme (`<html data-theme="caribbean">`, not switched on) swaps these seven for `#007F95 #0098B2 #00596A #BDEAF2 #D2F0F6 #B2E5EF rgba(0,127,149,.10)`.

## Neutrals

| Hex | Variable | Used for |
|---|---|---|
| `#0E0E10` | `--ink` | text, black buttons, bars |
| `#3B3B42` | `--text-2` | secondary text |
| `#6B6B73` | `--muted` | captions, labels |
| `#FFFFFF` | `--surface` | page and card background |
| `#E6E6EA` | `--rule` | dividing lines |
| `#EDEDF1` | `--track` | empty bar track |
| `#CFCFD6` | `--disabled` | disabled controls, input underlines |
| `#D9D9DF` | `--ruler-future` | future days on the day ruler |
| `#FAFAFB` | `--hover-row` | row hover |
| `#F6F6F8` | `--hover-index` | panels, hover, wells |

## Warning (yellow) and danger (red)

| Hex | Variable | Used for |
|---|---|---|
| `#E9A800` | `--warn` | warnings, "close to the limit" |
| `#B88400` / `#F2B705` | `--g-warn-*` | warning bar gradient, dark to light |
| `#8A6200` | (literal) | warning text such as "Needs a look" |
| `#C93030` | `--danger` | errors, over the limit |
| `#8E1F1F` / `#DA4444` | `--g-danger-*` | danger bar gradient, dark to light |

## Smaller ones (set where they are used, not as variables)

| Hex | Where |
|---|---|
| `#4A4A52` | end of the black bar gradient (`--g-ink-*`) |
| `#8E8E98` | nav icons, the daily-average line |
| `#9A9AA6` | "Carried over" block in the Now flow chart |

The Plan page colours its category swatches with a nine-step grey ramp (`RAMP` in `frontend/src/features/plan.ts`, values `--ramp-0` to `--ramp-8`), which flips in dark mode.

The Google Pay hand-off page (`frontend/src/app/pay/route.ts`) has its own small dark palette: `#111` page, `#2A2A2A` buttons, `#EEE` text.

## Dark mode

Choose it in **Account > Appearance**: System (follows the device), Light or Dark. The choice is saved in the browser (`localStorage`, key `lbstash-mode`), so it applies to that device only. A small script in `<head>` sets `data-mode="light"` or `"dark"` on `<html>` before the first paint, so a dark page never flashes white. All the work is in CSS variables: `:root[data-mode="dark"]` in `globals.css` gives every name below a new value, and nothing else in the app needs to know which mode is on.

Rules that keep both modes working:

- **Text on a filled colour** uses `--on-ink`, `--on-accent` or `--on-danger`, never `#fff`. A black button is a light button in dark mode.
- **A card, menu or input** sitting above the page uses `--raised`, never `#fff`.
- **Never write a literal grey or white** in a stylesheet or inline style. Use a variable, or add one with a dark value. The two exceptions are QR codes (they must stay white to scan) and the switch knob.

| Variable | Light | Dark | Used for |
|---|---|---|---|
| `--surface` | `#FFFFFF` | `#0E0E10` | page background |
| `--raised` | `#FFFFFF` | `#17171B` | menus, inputs, chips, buttons |
| `--ink` | `#0E0E10` | `#ECECF0` | text, borders, filled buttons |
| `--text-2` | `#3B3B42` | `#C4C4CC` | second-level text |
| `--muted` | `#6B6B73` | `#9A9AA6` | captions |
| `--rule` | `#E6E6EA` | `#2A2A31` | hairlines |
| `--track` | `#EDEDF1` | `#26262C` | empty bar track |
| `--disabled` | `#CFCFD6` | `#3C3C45` | borders, disabled, scrollbar |
| `--hover-row`, `--hover-index` | `#FAFAFB`, `#F6F6F8` | `#17171B`, `#1B1B20` | row and index hover |
| `--accent` | `#00875A` | `#00A06B` | green, lighter so it reads on dark |
| `--accent-pale`, `-ribbon`, `-ribbon-hover` | `#C9EEDD` `#D8F3E7` `#B3E6CD` | `#12372A` `#113026` `#17463A` | big glyphs, flow ribbon |
| `--accent-dark`, `--accent-light` | `#005C3D`, `#00A06B` | `#00875A`, `#2DC890` | bar gradient ends |
| `--danger` | `#C93030` | `#F2706A` | errors, delete |
| `--warn-text` | `#8A6200` | `#F2B705` | warning text |
| `--on-ink` | `#FFFFFF` | `#0E0E10` | text on an `--ink` fill |
| `--on-accent` | `#FFFFFF` | `#06140E` | text on an `--accent` fill |
| `--on-danger` | `#FFFFFF` | `#0E0E10` | text on a `--danger` fill |
| `--on-ink-2` | `#C9C9D2` | `#55555F` | second line in tooltips |
| `--placeholder` | `#B1B1BA` | `#5F5F69` | input placeholder |
| `--ribbon-neutral` | `#C9CDDB` | `#34384A` | grey flow ribbon on hover |
| `--wash-neutral` | `#F3F3F6` | `#1E1E24` | plan split bar background |
| `--hover-wash` | `rgba(14,14,16,.04)` | `rgba(236,236,240,.06)` | chart column hover |
| `--ramp-0` to `--ramp-8` | `#0E0E10` to `#EDEDF1` | `#ECECF0` to `#222228` | Plan category greys (reversed) |

The alternative blue-green theme also has a dark version (`#00A5C0 #0F3640 #0E2F38 #154553 rgba(0,165,192,.16) #007F95 #2DC4DC`).
