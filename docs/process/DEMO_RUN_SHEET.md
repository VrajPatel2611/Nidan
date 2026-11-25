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

**4b. Stage the clinician's queue.** The step above publishes all ten, which
leaves Act 3 with nothing to review. This returns three to draft and assigns
them to Dr Anita Verma — seven stay published for the learner.

```bash
python scripts/seed_demo_accounts.py --stage-review-queue
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

## Act 3 · the clinician (`localhost:8000/admin/reviews`)

This is the act that shows the launch gate working, and it is worth the
cookie swap. Sign in as **`demo.reviewer@example.com`** — the console will say
**Dr Anita Verma** — and repeat the cookie step with her token.

**Three cases are already assigned to her**, deliberately left as drafts:

- The Chest Pain Trap — *GERD, specifically NSAID-induced · trap: cardiac*
- The Faint That Was Not a Faint — *severe calcific aortic stenosis · trap: vasovagal faint*
- The Bleeding That Was Already Explained — *colorectal carcinoma · trap: haemorrhoids*

1. **The queue.** "Assigned to me (3)". Each row carries the real diagnosis
   and the real trap, so the clinician knows what they are being asked about
   before they open anything.
2. **Notice what is missing.** The sidebar has Dashboard and Case bank, but
   `/admin` and `/admin/cases` return the **same blank 404 an anonymous
   visitor gets**. A reviewer reads drafts and writes reviews, and nothing
   else. That is `current_reviewer()` and the five-actor model in one click —
   worth showing, because it is a security property you can demonstrate
   rather than assert.
3. **Open one in Playtest.** The clinician plays the case as a learner would,
   on the left, with the rubric on the right.
4. **Scroll to "Case facts · what you are scoring".** The ground truth: the
   correct diagnosis and every accepted and partial synonym, the trap and its
   keywords, all six contradictory clues, the required topics, every
   examination finding and investigation result with the **key** ones marked,
   and the persona brief behind a disclosure.

   Say the line here: *the rubric asks whether the case is internally
   consistent and whether it is solvable from the information given, and
   neither question can be answered from the student view — so the reviewer
   is shown the case, and the learner never is.* Point at the chest-pain
   case's serial troponins and normal ECG sitting beside an OGD showing LA
   Grade B oesophagitis. That is what "internally consistent" means, and a
   clinician can check it in ten seconds from this panel.
5. **Score it.** Four dimensions, 1–5. **Approve stays disabled until all
   four are scored** — and Request changes and Reject both require a comment.
6. **Approve.** The row leaves "Assigned to me" and appears under Completed
   with the scores and the comment, attributed and timestamped.
7. **Switch back to the admin cookie and publish it.** The Publish button is
   on the same page but **only an admin sees it** — approving and publishing
   are different acts by different people. It is disabled until an approving
   review exists.
8. **The gate itself.** Migration 007's `require_clinical_approval` trigger
   refuses any flip to `published` without an approving `clinical_reviews`
   row. It is a database trigger, not application code, so it cannot be
   bypassed from the app at all — `publish_for_demo.py` goes *through* it by
   inserting a review, never around it.

### Afterwards, and say this if asked

**Nothing Dr Anita Verma approves counts towards the launch gate.** She is a
demo account with a plausible name so the console looks like itself on a
projector, and that is precisely why it has to be said out loud: a
`clinical_reviews` row signed by a plausible clinician is indistinguishable a
month later from one a real clinician wrote. The seven already-published
cases are signed "Demo Fixture (not a clinician)" for the same reason.

One command removes every review any demo account recorded, returning
published versions to draft first so migration 007 is never violated:

```bash
python scripts/seed_demo_accounts.py --reset-reviews
```

Then put the bank back the way the learner act needs it:

```bash
python scripts/publish_for_demo.py --all
```

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
