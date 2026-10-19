# apps/web (Next.js 16, React 19, SWR, CSS modules)

```
src/
  app/            routes. (app)/ = signed-in pages with the shell; sign-in, create-account, secure, reset = auth pages
    globals.css   design tokens + shared classes (one definition each, see docs/ui-spec/00-design-system)
    (app)/<page>/page.tsx + page.module.css + the page's own parts (rows, wells, steps)
  components/     shell.tsx (AppShell, AccountShell, header, menu, ruler), ui.tsx (primitives), icons.tsx, auth-frame.tsx, check-panel.tsx
  features/       one pure view-model per page or area: now, ledger, plan, limits, repeats, trends, credit, unread, account, devices, setup
  common/         pure helpers: money, format, amount-input, time, chart, tags, password, metrics (import from '@/common')
  contracts/      API response/request types (zod schemas, used as types only; import from '@/contracts')
  lib/            api.ts (fetch + SWR + CSRF + refresh), me.ts (useMe, useToday), browser.ts (clipboard, download, flash), use-amount-field.ts
test/             vitest unit tests for features/ and common/ (alias @ -> src)
```

- Pages call `features/*` for decisions and `lib/api` for I/O. Keep components dumb.
- The shell is `.app { height: 100vh }`; only `.scroller` and panels scroll. Do not set `align-content` on `.scroller`: it must stretch so panels fill the window.
- Scroll regions need a `min-height` floor, otherwise they collapse to zero in the narrow (wrapped) layout.
- Dev: `GATEWAY_URL=http://127.0.0.1:3000 npm run dev` in `apps/web` (port 3100, rewrites `/api` to the gateway). `next/font/google` fetches fonts at build time (needs network once).
- Docker: build context is `apps/web`; standalone server is `.next/standalone/server.js`.
- Spec drift fixed so far: panels fill height, Limits/Setup lists no longer clipped, Now has no CHECK link (CHECK lives on the Ledger), auth header height is fixed at 56px.
