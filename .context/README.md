# .context: read this instead of the whole repo

Short notes per area so an agent (or you) does not re-read thousands of lines. Read the one file for the area you touch, plus `conventions.md`. Update the note in the same change when you move or rename things.

| File | Area |
|---|---|
| `conventions.md` | rules every change follows: comments, structure, money, verification |
| `web.md` | `apps/web`: layers, where each page's code lives, UI gotchas |
| `backend-shared.md` | `packages/bt`: common, crypto, contracts, db, queue, clients, kit |
| `services.md` | the eight services: what each owns and where its code is |
| `infra.md` | docker, compose, env, scripts, how to run and verify locally |
| `status.md` | what was cleaned, what is known broken, what is next |

Source of truth for behaviour: `README.md` (product), `docs/ARCHITECTURE.md` (where code lives), `docs/ui-spec/` (UI).
