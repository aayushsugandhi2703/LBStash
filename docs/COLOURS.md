# Colours

Every colour the web app uses. The shared ones are CSS variables at the top of `apps/web/src/app/globals.css`; change a variable there and rebuild the web image (`docker compose build web && docker compose up -d web`) to change it everywhere.

**All in one line:**
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

The logo mark follows `--accent` in the app (`apps/web/src/brand/logo.tsx`); the standalone files in `apps/web/public/brand` use `#00875A`.

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
| `#B1B1BA` | input placeholder text |
| `#C9C9D2` | second line in tooltips |
| `#C9CDDB` | flow-chart ribbon hover (grey) |
| `#F3F3F6` | plan split bar background |
| `#9A9AA6` | "Carried over" block in the Now flow chart |

The Plan page colours its category swatches with a grey ramp (`RAMP` in `apps/web/src/features/plan.ts`): `#0E0E10 #2C2C33 #4A4A53 #6B6B73 #8E8E98 #B1B1BA #CFCFD6 #E3E3E8 #EDEDF1`.

The Google Pay hand-off page (`apps/web/src/app/pay/route.ts`) has its own small dark palette: `#111` page, `#2A2A2A` buttons, `#EEE` text.
