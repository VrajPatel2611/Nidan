# Nidan web app

The learner-facing app — Next.js + TypeScript (`ADR-0006`). The admin console
is not here; it stays Jinja + HTMX in `nidan/web/admin/`.

```bash
cd web
npm ci                     # once
cp .env.example .env.local # then fill in the two Supabase values
npm run dev                # http://localhost:3000 — the Flask API must be on :8000
```

| Command | Does |
|---|---|
| `npm run dev` | dev server on :3000 |
| `npm run build` | production build |
| `npm test` | unit tests (Vitest) |
| `npm run typecheck` · `npm run lint` | TypeScript · ESLint |
| `npm run gen:api` | regenerate `src/api/schema.ts` from `../openapi.yaml` |
| `npm run check:api` | fail if that file is stale — CI runs this |

**Change `openapi.yaml`, then run `npm run gen:api` and commit both.** The
types are generated, never edited (`T-032` criterion 2).

## Layout

```
src/
  app/                    routes (App Router)
    (auth)/               S-02 signup · S-03 login · S-04/05 reset · S-06 verify
      actions.ts            every auth call, server-side
    auth/callback/        S-22 — OAuth and every email link land here
    auth/signout/         POST only
    dashboard/ welcome/   placeholders for T-033
  proxy.ts                route protection (UX_SPEC §6.1.4) — Next 16's middleware
  components/ui/          the UX_SPEC §3.5 component library
  components/auth/        the auth forms
  lib/                    env · Supabase clients · API client · redirects · validation
  api/schema.ts           GENERATED from openapi.yaml
  styles/tokens.css       UX_SPEC §3.1–3.4 as CSS variables
```

## Two rules this app is built around

- **No browser Supabase client.** Sessions live in httpOnly cookies
  (`UX_SPEC` §6.1.3), so every auth call is a server action, a route handler
  or the proxy. Adding `createBrowserClient` would need the cookies readable by
  JavaScript, which is the thing §6.1.3 rejects.
- **Every protected server action checks the user itself.** The proxy is not
  enough: Next runs server actions as POSTs to their page, and a matcher change
  can drop them out of its reach without anything failing.
