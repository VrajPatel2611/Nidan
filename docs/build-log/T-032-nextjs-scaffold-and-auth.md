# T-032 · Next.js scaffold and auth

| | |
|---|---|
| **Task** | T-032, BUILD_PLAN Phase 3 |
| **Status** | 🟡 Built — **not yet verified against the live Supabase project** (§6) |
| **Branch** | `feat/t-032-nextjs-scaffold` |
| **Estimated** | 4 days |
| **Specification** | `ADR-0006` · `UX_SPEC` §3, §6.1, S-02…S-06, S-22 |
| **Behaviour change** | A new app in `web/`: Next.js 16 + TypeScript, with the design tokens, a typed API client generated from `openapi.yaml`, the 19-component library, and Supabase sign-up, log-in, password reset and email verification. The Flask app is unchanged. |

---

## 1 · Summary

```
web/package.json · package-lock.json      Next 16.4.5 · React 19.3 · TypeScript 5.9 · @supabase/ssr 0.12
web/src/styles/tokens.css                 UX_SPEC §3.1–3.4 as CSS variables
web/src/api/schema.ts                     GENERATED from ../openapi.yaml
web/scripts/check-api-types.mjs           fails CI when schema.ts is stale
web/src/components/ui/                    the §3.5 inventory — 19 components
web/src/proxy.ts                          route protection, §6.1.4
web/src/app/(auth)/                       S-02 · S-03 · S-04 · S-05 · S-06, and actions.ts
web/src/app/auth/callback/                S-22 — OAuth and every email link
web/src/app/auth/signout/                 §6.1.7
web/src/lib/                              env · Supabase clients · API client · redirects · validation
.github/workflows/ci.yml                  + "Web app" job
openapi.yaml                              duplicated key fixed (§4.1)
```

**118 tests** (Vitest), plus `tsc`, ESLint, the stale-types check, `npm audit`
(0 vulnerabilities) and a production build — all of which the new CI job runs.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Next.js + TypeScript; tokens from §3.1–3.4 as CSS variables | `tokens.css` | `tokens.test.ts` **parses UX_SPEC.md** and checks all 36 tokens' values |
| 2 | Types generated from openapi.yaml; CI fails if stale | `npm run gen:api` · `check:api` · CI job | broken on purpose: an appended line → exit 1, restored → exit 0 |
| 3 | Supabase auth: signup, login, reset, verification (S-02…S-06) | `(auth)/actions.ts`, the forms, `auth/callback`, `proxy.ts` | unit tests for redirects and validation; route protection probed with curl against a production build. **Not against live Supabase** — §6 |
| 4 | Component library per §3.5 | `components/ui/` | `ui.test.tsx` **reads the §3.5 table** and fails if a listed component is not exported; behaviour tests for the focus trap, keyboard tabs, the 4 s toast, loading buttons, field errors |

---

## 3 · Decisions

### 3.1 No browser Supabase client — every auth call is on the server

§6.1.3 requires the session in **httpOnly** cookies so an XSS bug cannot read
the refresh token. `@supabase/ssr`'s browser client needs the cookies readable
by JavaScript, so it is not used at all: sign-up, log-in, OAuth, reset and
resend are server actions; the code exchange is a route handler; refresh happens
in the proxy. `cookieOptions` forces `httpOnly`, `SameSite=Lax` (Strict breaks
the OAuth callback) and `Secure` in production.

### 3.2 `proxy.ts`, not `middleware.ts`

Next 16 renamed the convention (its own docs, bundled in `node_modules/next`).
Its docs also warn that server actions run as POSTs to their page and can fall
outside the proxy's matcher silently — so `setNewPassword`, `/welcome` and the
dashboard ask Supabase for the user themselves.

### 3.3 Everything is private unless listed

`lib/routes.ts` lists the public paths; anything else redirects to
`/login?next=…`. A new page is private until someone decides otherwise.
`/case/*` is public for the anonymous trial (§6.1.4), ready for T-034.

### 3.4 `?next=` is validated, and the landing order is a tested function

`safeNext` discards absolute URLs, `//host`, `/\host`, control characters and
anything that resolves off-origin — eleven cases tested. `landingPath` is
§6.1.5's table in priority order, pure, and tested row by row.

### 3.5 The spec's copy, and its two privacy rules

Copy is S-02…S-06's, word for word. The forms never reveal whether an account
exists: "already registered" goes to the same *check your inbox* screen as a new
signup, a wrong password and a deleted account read the same, and the reset
request confirms identically either way.

### 3.6 `/reset/{token}` became `/reset/new`

With Supabase's PKCE flow the recovery token is exchanged at `/auth/callback`,
which opens a recovery session. S-05 therefore needs a session, not a token in
its URL. Email links carry `type=signup` / `type=recovery` so an expired one
lands on the screen it belongs to (S-05, S-06) rather than a generic error.

### 3.7 Dependencies kept short (`ADR-0006`)

Five runtime packages: `next`, `react`, `react-dom`, `@supabase/ssr` and its
peer `@supabase/supabase-js`, plus `server-only`, which fails the build if
server code is ever imported into a browser bundle. No CSS framework or
component library — the tokens are plain CSS variables and §3.5 is small.
TypeScript is pinned to 5.9 because `openapi-typescript` requires 5.x.

### 3.8 Placeholders, not screens

`/`, `/welcome` and `/dashboard` exist so every redirect lands somewhere. The
real screens are S-01 (not scheduled) and T-033. `/welcome` already does the one
thing S-22 needs of it: it retries `POST /me` when sign-in could not create the
profile.

---

## 4 · Found along the way

### 4.1 `openapi.yaml` was invalid YAML

`DELETE /me` had two `description:` keys — T-030 slice 5 added the "Still
returns 501" text above the original without removing it. PyYAML, which the
backend's tests use, silently keeps the last of two keys, so nothing noticed.
The type generator's strict parser refused the file outright. Merged into one
description, nothing lost; `tests/test_openapi.py` still passes. **The new CI
job is now the only strict parse the contract gets.** Handed to Vraj (V-7).

### 4.2 The root `.gitignore` hid `web/src/lib/`

Its Python template ignores `lib/`, which also matches `web/src/lib/` — the
Supabase clients, redirects and API client. Locally everything worked, because
the files were on disk; a clone would have failed to build. Re-included from
`web/.gitignore`; the Python rule is untouched.

### 4.3 An outage read as "wrong password" — fixed 10 Nov

With the anon key in place the project turned out to be unreachable (§6), and
that showed the gap: Supabase failing to answer at all came back through the
generic branch, so log-in said "That email or password doesn't match." and the
reset form claimed to have sent a link. `isUnreachable()` now answers network
errors, DNS failures and 5xx with "We can't reach the sign-in service right
now" (U5: fail visibly). 13 action tests cover each Supabase answer; switching
the check off turns 6 of them red.

Running the real dev server also caught what the tests could not: a
`"use server"` module may export async functions only, and exporting the
message string from `actions.ts` failed every page with a 500. It lives in
`lib/authCopy.ts`.

### 4.4 jsdom wants Node 22.22+

This laptop has 22.19 and the tests pass with a warning. CI uses the latest
22.x.

---

## 5 · Not in this task

- **S-23 · Session expired** — a modal over a consultation, so it belongs with
  T-034 where it has something to sit on.
- **S-01 · Landing** — not scheduled in `BUILD_PLAN`.
- **"An email goes to the existing account noting the attempt"** (S-02) — that
  is Supabase's mail, configured in its dashboard, not this app.

---

## 6 · Before this is called done — needs the live project

None of the following can be checked from code; all need the Supabase project.

**10 Nov: the anon key arrived, and the project does not resolve.** The key is
genuine (`role: anon`, issued 28 Oct, project ref `xtrqmusmardmmzsptuwa`), but
`xtrqmusmardmmzsptuwa.supabase.co` is NXDOMAIN from Google and Cloudflare DNS
alike, while `supabase.co` resolves — the same answer as an invented ref. The
project is paused or deleted; the free plan pauses inactive projects. Vraj to
restore it (handoff V-8). Everything below waits on that.

1. A real sign-up → verification email → callback → `POST /me` → `/welcome`.
2. Log in, sign out, log back in.
3. Password reset end to end, and that other sessions are signed out.
4. In the Supabase dashboard (Vraj, V-7): `http://localhost:3000/auth/callback`
   in **Redirect URLs**; Google and Apple **providers** enabled, or their
   buttons will say "We couldn't reach Google"; whether **Confirm email** is on
   (it decides whether S-03's "unverified email: login succeeds" can happen);
   and leaked-password protection if the plan has it.

When those pass, tick T-032 in `BUILD_PLAN` and regenerate `STATUS.md`.

---

## 7 · Verification

```bash
cd web
npm ci
npm run check:api        # src/api/schema.ts matches openapi.yaml
npm run typecheck        # clean
npm run lint             # clean
npm test                 # 118 passed
npm audit --omit=dev     # 0 vulnerabilities
npm run build            # 11 routes + proxy
```
