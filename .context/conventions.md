# Conventions

- **Comments:** only where the code cannot say why. One short line, plain words. No dividers, no "port of", no README section numbers unless they help. Docstrings: one line; two only when a rule is non-obvious.
- **Common code:** shared Python goes in `packages/bt/src/bt/<topic>`; shared web code in `apps/web/src/common` (pure) or `components/` (React). Never copy a helper between services or pages.
- **Dead code:** delete it, do not comment it out. Exports nobody imports are dead.
- **Money:** integer paise everywhere; format only at the edge (`format_inr`, `common/format.ts`). Month and day maths use the user's time zone.
- **Layout rule for web pages:** a page folder holds its `page.tsx`, `page.module.css` and its own parts. Logic shared by two pages goes to `features/` or `common/`.
- **Downloads:** never download or install anything from the internet without asking the user first, even in auto mode.
- **Tests:** do not add or fix tests until the user says so. Existing web tests run with `npx vitest run` in `apps/web`; backend tests are known broken (see `status.md`).
- **Verify a change:** web `npx tsc --noEmit` + `npx vitest run`; Python `ruff check` + import smoke; behaviour via `scripts/e2e.py` against a running stack.
