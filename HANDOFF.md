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

- [ ] **V-1** (2026-10-28, from Yogesh) · **T-023 blocker: reviewers cannot read
  drafts or record a review.** `@require_reviewer` lets a reviewer into the
  console, but their requests run as `nidan_app` (`current_actor()`), which
  cannot see draft `case_versions` (RLS: `read_published_cases` only) and has no
  INSERT on `clinical_reviews`. Only `AdminUser` / `nidan_admin` has both
  (migration 023). So a reviewer cannot open a draft in Playtest or submit the
  rubric. Needs a reviewer-scoped actor or role (draft SELECT + `clinical_reviews`
  INSERT, nothing else) and a repository for `clinical_reviews`: insert a review,
  list reviews for a version, "has an approving review?". Files are `infra/`,
  `api/auth.py`, `migrations/` — Yogesh's brief forbids him touching them.
  Done when a `@require_reviewer` route can load a draft and insert a review.

- [ ] **V-2** (2026-10-28, from Yogesh) · **T-023 blocker: nowhere to store a
  reviewer assignment.** T-023 criterion 1 is "assign a version to a reviewer",
  and the queue has an "Assigned to me" tab, but no table or column records who
  is assigned to which version. Decide the storage (new table, or a column on
  `case_versions`) and add the migration + repository methods (assign, list
  assigned to me, list pending). Done when Yogesh can call them from
  `nidan/web/admin/reviews/`.

- [ ] **V-3** (2026-10-28, from Yogesh) · **Publish has no repository method.**
  T-023 needs "publish this version" that sets `status = 'published'`, so the
  `enforce_clinical_approval` trigger and the `one_published_version_per_case`
  index can fire. Add it to `CaseRepository` (it can raise the trigger and
  unique-violation errors as typed exceptions so the route can return 409).

- [ ] **V-4** (2026-10-28, from Yogesh) · **Merge `docs/phase-2-briefs`.** The
  in-repo briefs (`00_START_HERE.md`, T-022, T-023) are still unmerged, so
  Yogesh is working from copies in his Downloads folder — the exact staleness
  the briefs' README warns about.

- [ ] **V-5** (2026-10-28, from Yogesh) · **How does Yogesh sign in to `/admin`
  locally?** His `.env` has no `SUPABASE_URL` / `SUPABASE_JWT_AUDIENCE`, and
  there is no profile with `platform_role = 'admin'` on his local database.
  Needed to click through Playtest by hand. Send the values **privately**, and
  write the steps here.

## Inbox — for Yogesh

- [ ] **Y-1** (2026-10-28, setup) · Repoint the remote — the repo was renamed:
  `git remote set-url origin https://github.com/VrajPatel2611/nidan.git`

---

## Done

- **2026-10-28** · Yogesh's laptop brought up to date: local `main` = GitHub
  `main` (`384266c`, T-021 merged), venv reinstalled as `nidan`, Docker running,
  607 tests pass with none skipped, local DB migrated to `023`, `DATABASE_URL`
  added to `.env`.
