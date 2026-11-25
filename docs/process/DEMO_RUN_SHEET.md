# Demo run sheet

Everything needed to run Nidan on Vraj's laptop in front of an audience, in the
order it happens. Verified end to end on 25 November 2026.

**Accounts and the password are in `logs/demo-accounts.txt`** (gitignored).
Regenerate with `python scripts/seed_demo_accounts.py`.

---

## Why there are two apps on two ports

This trips people up, so get it straight before the day:

| | what it is | port |
|---|---|---|
| **Next.js** | the **learner's** app — sign in, consultation, feedback, history | `localhost:3000` |
| **Flask** | the `/v1` JSON API **and** the **admin console** at `/admin` | `localhost:8000` |

The learner never sees :8000 and the administrator never sees :3000. They share
one database and one Supabase project.

---

## T-30 min · bring the stack up

Run each from `/Users/vrajpatel/Desktop/Nidan`.

**1. Database.**

```bash
docker compose up -d db
```

**2. Stop the stale `app` container.** It takes port 8000 on the IPv6 wildcard
and serves an image baked weeks ago with no source mount, so the web app talks
to old code and nothing says so. It has `restart: unless-stopped`, so **it comes
back every time Docker Desktop restarts** — do this every session.

```bash
docker compose stop app
```

**3. Migrations.** `alembic` reads `os.getenv("DATABASE_URL")` and does *not*
read `.env`, so it must be exported.

```bash
export DATABASE_URL="postgresql://nidan:nidan_local_dev_only@localhost:5433/nidan"
```

```bash
alembic upgrade head
```

**4. Publish the cases.** Every case is a draft, and `POST /v1/sessions` answers
`no_cases_available` until one is published.

```bash
python scripts/publish_for_demo.py --all
```

**5. The API.**

```bash
python -m nidan
```

**6. The web app — `next start`, never `next dev`.** A dev server on this
machine stalls ~21 s on the first request to each route. A production build
serves in 2 s.

```bash
cd web && npx next build && npx next start
```

The build takes ~35 min on this machine, so **build the night before**. If
`web/.next` already exists and nothing in `web/` changed, `npx next start`
alone is enough.

**7. Check the model key.** No test makes a network call, so nothing else
tells you the configured Groq model still exists.

```bash
python test_api.py
```

---

## T-10 min · the admin cookie

The console has no sign-in page — `ADR-0002` gives Supabase the job of issuing
credentials. A browser cannot send an `Authorization` header, so the token goes
in a cookie. **It lasts about an hour**, so do this shortly before, not the
night before.

Get a token for `demo.admin@example.com` — the password is in
`logs/demo-accounts.txt`, and `LOCAL_ADMIN_ACCESS.md` §4 has the full command
that keeps it off the screen and out of shell history:

```bash
printf 'email: '; read -r EMAIL; printf 'password: '; read -rs PW; echo; PAYLOAD=$(EMAIL="$EMAIL" PW="$PW" python3 -c 'import os,json;print(json.dumps({"email":os.environ["EMAIL"],"password":os.environ["PW"]}))'); curl -s "$(grep NEXT_PUBLIC_SUPABASE_URL web/.env.local | cut -d= -f2-)/auth/v1/token?grant_type=password" -H "apikey: $(grep NEXT_PUBLIC_SUPABASE_ANON_KEY web/.env.local | cut -d= -f2-)" -H "Content-Type: application/json" -d "$PAYLOAD" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'
```

Then in the browser, open `http://localhost:8000/admin`, open DevTools →
Console, and paste `document.cookie = "sb-access-token=<token>; path=/"`,
then reload.

(`python scripts/seed_demo_accounts.py --show` lists the accounts and their
uids, but issues no token.)

**If `/admin` shows a blank `{"error":{"code":"not_found"}}`, the token has
expired.** Every refusal is an identical 404 by design (`UX_SPEC` §12.1), so it
tells you nothing — work through `LOCAL_ADMIN_ACCESS.md`'s table in order.

---

## Act 1 · the learner (`localhost:3000`)

1. **Landing page** → *Sign in*.
2. Sign in as **`demo.learner@example.com`**. This account is deliberately
   *not* onboarded, so you get the first-run flow.
3. **Onboarding** — pick "Medical student", year 4.
4. **Dashboard** — shows the free-tier allowance. Say the line here: *the
   allowance is shown before you start and never during a consultation.*
5. **Start a consultation** → case preview → begin.
6. **Ask two or three questions.** Suggested, for the DKA case:
   - "Have you been unusually thirsty or passing more urine than normal?"
   - "Have you lost any weight recently?"
   - "Have you been unwell with anything in the last few weeks?"
7. **Point at what is missing.** No question counter, no coverage meter, no
   topic hints. *A visible metric teaches the metric, not the skill* (`PRD` P2).
8. **Order an examination and a test** — these do not consume questions.
9. **Submit a diagnosis**: "Diabetic ketoacidosis".
10. **The feedback screen** — this is the point of the whole project:
    - the headings are *Diagnostic focus · History completeness · Evidence
      exploration*. **No bias vocabulary anywhere in the product** (`PRD` P1).
    - the scores are deterministic Python; the LLM only writes the prose and
      voices the patient (`ADR-0005`).
    - every judgement cites the learner's own questions (`ADR-0004`).
11. **Sign out**, then sign back in. History and progress are intact.

### ⚠️ Do not sign up a brand new account live

It will fail with *"We couldn't finish setting up your account."* Supabase
creates the cloud user fine, but `profiles.id` has a foreign key to
`auth.users`, which on a laptop is migration 001's three-column stub that
nothing populates. **This is the architecture, not a bug**, and it resolves
itself the day `DATABASE_URL` points at Supabase (`T-045` criterion 1).

If asked, that is the honest answer, and it is a good one. Use
`demo.student@example.com` as the spare if the first account gets into a state.

---

## Act 2 · the administrator (`localhost:8000/admin`)

1. **Dashboard.** Every figure is read from the database. Two that an audience
   might expect are deliberately absent — *sessions today* and *completed* —
   because `sessions` has RLS on and an admin scope cannot read learners'
   sessions. That is worth saying out loud: the console cannot see a learner's
   consultation, by policy, not by omission.
2. **Case bank** — ten cases, their slugs, specialties, versions and statuses.
3. **Create a case.** Type a slug in the box top-right (e.g.
   `abdominal-pain-appendicitis`) → **+ New case**. It opens the editor on a
   valid scaffold: all four invariants green.
4. **The editor**, section by section: Patient · Truth · **The Trap** · History
   · Clues · Examination · Tests · Persona.
5. **The money moment — invariant C-4.** In *The Trap*, add a word to **Anchor
   Keywords** that already appears in a **contradictory clue** (e.g. add
   `burning`). The Validation Status panel goes red and **Save Draft is
   blocked**. Say: *this exact overlap cost 14 % sensitivity in the
   confirmation-bias detector, so the editor refuses to save it.* Then remove
   it and watch it go green.
6. **Playtest** — play the draft as a learner with the engine's view alongside.
   Uses the **last saved** content, so save first.
7. **Review queue** (`/admin/reviews`) — assign a reviewer, record a decision
   against the four-dimension rubric, publish.
8. **The gate.** A case cannot be published without an approving clinical
   review. That is **migration 007's database trigger**, not a convention — it
   cannot be bypassed from the application at all.

### Four screens to skip

**Content**, **AI Ops**, **Users** and **System** are shells. They are
`UX_SPEC` A-06, A-07, A-08 — Phase 4, Yogesh's next two tasks (T-043, T-044).
If asked, that is the answer; do not click them for effect.

---

## Act 3 · the reviewer (optional)

Sign in as `demo.reviewer@example.com` and repeat the cookie step. The reviewer
sees **only** `/admin/reviews`; every other admin URL is the same blank 404 an
anonymous visitor gets. Worth showing — it is a one-line demonstration of
`current_reviewer()` and the five-actor model.

---

## If something breaks

| symptom | cause |
|---|---|
| `/admin` is a blank 404 | token expired (~1 h). Get a new one |
| Web app says the API is unreachable | the stale `app` container is back. `docker compose stop app` |
| `no_cases_available` on starting a consultation | `python scripts/publish_for_demo.py --all` |
| `alembic` says "No database URL" | `export DATABASE_URL=...` — it does not read `.env` |
| Patient replies 503 `patient_unavailable` | Groq model retired or the circuit breaker is open. `python test_api.py` |
| First click on a page takes 20 s | you are on `next dev`. Use `npx next start` |

---

## Afterwards

```bash
python scripts/seed_demo_accounts.py --undo
```

Removes the local rows. The four Supabase accounts stay — deleting one needs
the `service_role` key, which no script here is allowed to touch.
