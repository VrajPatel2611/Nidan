# Nidan handoff — Yogesh ⇄ Vraj

Two laptops, one Claude account, no shared chat history. Claude on one laptop
cannot see or message Claude on the other. **This file is how work crosses
between them.** It lives on its own branch, `handoff`, which shares no history
with `main`: no pull request, no CI, no merge conflicts with code.

---

## For Claude — read this part every session

**At the start of a session**, before any task work:

```bash
git fetch origin handoff
git show origin/handoff:HANDOFF.md
```

Tell the person what is open in **their** inbox. If an item blocks the task
they asked for, say so before starting.

**At the end of a session**, or the moment something is found that the other
person must do, add it to **their** inbox and push:

```bash
git fetch origin handoff
git worktree add ../nidan-handoff handoff     # first time only, on each laptop
cd ../nidan-handoff && git pull --ff-only
# edit HANDOFF.md
git commit -am "handoff: <one line>" && git push origin handoff
```

Never check out `handoff` in the main working folder: it has none of the
project's files, and switching to it would look like the whole repo vanished.

**Rules**

- Write to the *other* person's inbox. Your own items are theirs to send you.
- One item = what, why, where (file / branch / PR), and what "done" looks like.
  Written so the other Claude can act on it cold, with no chat history.
- Number items `V-n` (for Vraj) and `Y-n` (for Yogesh). Never reuse a number.
- When an item is done, move it to **Done** with the date and the commit or PR.
  Do not delete items.
- **No secrets.** No keys, tokens, passwords, `.env` values. This is on GitHub.
  Say "sent privately" and send them some other way.
- Dates as YYYY-MM-DD. British English.

---

## Inbox — for Vraj

*Empty — V-1 to V-5 done 2026-10-28, see below.*

## Inbox — for Yogesh

- [ ] **Y-1** (2026-10-28, setup) · Repoint the remote — the repo was renamed.
  Note the capital N; the old URL still works but every push prints a redirect
  warning: `git remote set-url origin https://github.com/VrajPatel2611/Nidan.git`

- [ ] **Y-2** (2026-10-28, from Vraj) · **T-023 backend is built and MERGED —
  V-1, V-2 and V-3 are all cleared, and nothing is blocking you.** PR #26 went
  into `main` as `6680642`. **`git pull` and it is there.** Verified on the
  merged result: 654 tests pass (235 against real Postgres), ruff, mypy,
  import-linter and the detector check all green. Then:

  ```python
  from nidan.api.auth import current_reviewer, current_admin, require_reviewer
  from nidan.infra.db.repositories import repo_scope

  with repo_scope(current_reviewer()) as db:          # @require_reviewer routes
      db.reviews.assigned_to_me()                     # "Assigned to me" tab
      db.reviews.pending()                            # "All pending" tab
      db.reviews.completed()                          # "Completed" tab
      db.reviews.for_version(version_id)              # reviews of one version
      db.reviews.is_author(version_id, reviewer_id)   # the reviewer≠author warning
      db.reviews.record(version_id, decision="approved",
                        scores={"clinical_plausibility": 5,
                                "internal_consistency": 4,
                                "trap_validity": 5, "solvability": 4},
                        comments="...")               # returns the review id

  with repo_scope(current_admin()) as db:             # @require_admin routes
      db.reviews.assign(version_id, reviewer_id)      # assigning is admin-only
      db.reviews.unassign(version_id, reviewer_id)
      db.reviews.has_approval(version_id)             # grey out Publish with this
      db.cases.publish(version_id)                    # may raise, see below
  ```

  Four things to know:

  1. **`current_reviewer()`, not `current_actor()`, on every `@require_reviewer`
     route.** That is what V-1 was: `current_actor()` runs as `nidan_app`, which
     cannot see a draft or insert a review. An admin on the review queue also
     gets `current_reviewer()` — reviewing is reviewing. Use `current_admin()`
     only for assigning and publishing.
  2. **Catch `RubricViolation`** from
     `nidan.infra.db.repositories.reviews`. It is raised for an approval with
     any dimension below 4, a `changes_requested`/`rejected` with no comment, a
     missing dimension, or a score outside 1–5. The message names what is wrong
     and is safe to show. You still disable the Approve button in the form —
     this is the backstop, not the user experience.
  3. **Catch `PublicationBlocked`** and **`AlreadyPublished`** from
     `nidan.infra.db.repositories.cases` around `publish()` — they are your 409.
     The first means no approving review; the second means another version of
     that case is already published. `publish()` is idempotent, so a double
     click is harmless.
  4. `record()` takes the reviewer from the scope. There is no `reviewer_id`
     argument, on purpose.

  Done when `nidan/web/admin/reviews/` can list the three tabs, assign, record a
  review and publish.

  **One migration to apply before the app will run:** `alembic upgrade head`
  takes your local database from 023 to 024. Without it every review route
  fails on a missing `review_assignments` table and a missing `nidan_reviewer`
  role, which will not look like a migration problem.

- [ ] **Y-3** (2026-10-28, from Vraj) · **Stop using the Downloads copies of the
  briefs.** Merged — PR #25, `docs/process/phase-2-briefs/`. `git pull` and read
  them there from now on.

  Only two files are left: `00_START_HERE.md` and `03_T-023_clinical_review.md`.
  The T-020, T-021 and T-022 briefs are **deleted** now those tasks are merged —
  a finished brief is one more document that can be picked up by mistake, which
  is exactly what went wrong on T-020. What was built is in the build logs.

- [ ] **Y-4** (2026-10-28, from Vraj) · **Signing in to `/admin` locally — V-5
  answered.** Steps below in the Notes section. The two `.env` values are
  **sent privately**, not here.

---

## Notes

### Signing in to `/admin` on a local machine (answers V-5)

The console has no login page of its own: `ADR-0002` says Supabase issues
credentials and the backend only verifies them, so a local sign-in means getting
a real Supabase token and letting the app verify it. Five steps.

**1 · Put the two values in `.env`.** `SUPABASE_URL` is **sent privately**.
`SUPABASE_JWT_AUDIENCE` is the Supabase default and is in `.env.example`
already:

```
SUPABASE_JWT_AUDIENCE=authenticated
```

**2 · Get an access token.** Either from the Supabase dashboard
(Authentication → Users → your user → generate a link), or by signing in
against the project's auth endpoint. The anon key for that call is **sent
privately**:

```bash
curl -s "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}' | python3 -m json.tool
```

Keep `access_token`. Note the `sub` claim inside it — that is your user id, and
step 3 needs it. Decode the middle segment to read it:

```bash
python3 -c "import base64,json,sys; t=sys.argv[1].split('.')[1]; print(json.loads(base64.urlsafe_b64decode(t+'=='*3))['sub'])" "<access_token>"
```

**3 · Give yourself an admin profile on your *local* database.** Supabase holds
the account; your local Postgres holds the profile, and they are joined by that
id. `profiles` references `auth.users`, so both rows are needed:

```bash
docker compose up -d db
psql "$DATABASE_URL" -c "INSERT INTO auth.users (id) VALUES ('<sub>') ON CONFLICT DO NOTHING;"
psql "$DATABASE_URL" -c "INSERT INTO profiles (id, platform_role) VALUES ('<sub>', 'admin') ON CONFLICT (id) DO UPDATE SET platform_role = 'admin';"
```

Use `'reviewer'` instead of `'admin'` to see the console as a clinician does —
worth doing once while building T-023, because that is the role that reaches the
review queue and nothing else.

**4 · Set the cookie.** `bearer_token()` accepts either an
`Authorization: Bearer` header or the `sb-access-token` cookie, and a browser
can only do the cookie. With the app running at `http://localhost:5000`, open
dev tools → Application → Cookies and add:

```
name   sb-access-token
value  <access_token>
path   /
```

**5 · Open `http://localhost:5000/admin`.**

**If you get a 404, that is the access control working, not a missing page.**
Every refusal returns an identical 404 — no token, expired token, signed in
without privilege (`UX_SPEC` §12.1). So a 404 means one of: the cookie is not
set, the token has expired (they last about an hour — redo step 2), or the
`profiles` row has the wrong id or `platform_role`. Check the last one with:

```bash
psql "$DATABASE_URL" -c "SELECT id, platform_role FROM profiles;"
```

---

## Done

- **2026-10-28** · **T-022 playtest merged** (PR #24) and a T-021 form fix
  (PR #27). Phase 2 is 3 of 4 tasks done; **T-023 is all that remains**, and it
  is the gate — approving a case is what lets the two clinicians start and the
  five remaining cases be written. `STATUS.md` regenerated: 19 of 34 tasks,
  36 d of 83.

- **2026-10-28** · **V-1, V-2, V-3** · T-023 backend built: `nidan_reviewer`
  role and `ReviewerUser` actor (reads drafts, inserts reviews, writes no
  content), `review_assignments` table, `ReviewRepository`, and
  `CaseRepository.publish()` with typed exceptions. Migration 024. Rubric floor
  enforced at the write, not only in the form. Both guards probed. **Merged
  2026-10-28, PR #26, `6680642`** — 654 tests pass on the merged result, 235 of
  them against real Postgres.

- **2026-10-28** · **V-4** · Phase 2 briefs brought up to date and **merged**
  (PR #25). T-020, T-021 and T-022 briefs retired as those tasks landed;
  `00_START_HERE.md` and the README now point at T-023 alone. Yogesh told in
  Y-3.

- **2026-10-28** · **V-5** · Local `/admin` sign-in steps written up in Notes
  above; the two `.env` values sent privately. Yogesh told in Y-4.

- **2026-10-28** · Yogesh's laptop brought up to date: local `main` = GitHub
  `main` (`384266c`, T-021 merged), venv reinstalled as `nidan`, Docker running,
  607 tests pass with none skipped, local DB migrated to `023`, `DATABASE_URL`
  added to `.env`.
