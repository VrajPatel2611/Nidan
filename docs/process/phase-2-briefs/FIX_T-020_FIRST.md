# Do this before anything else — get the T-020 pull request green

Your `admin` branch is red on two checks. Nothing is wrong with your code. Your
branch is just built on an older `main` than the one that exists now, so it
carries one test file that `main` has since updated.

**These exact commands have been run and verified** against `admin` at `1e617a7`
and `main` at `8aada17`. The result is `387 passed`, `ruff` clean, `mypy` clean.
Follow them literally and the build goes green.

---

## Step 0 · Push anything you have committed locally

A `git commit` only writes to your own machine. GitHub sees nothing until you
`git push`. GitHub still shows your branch at `1e617a7` — the commit from
21 September — so if you have committed since then, it has not left your laptop.

```bash
cd path/to/Nidan
git checkout admin
git status
```

- If it says **`Your branch is ahead of 'origin/admin' by N commits`** —
  run `git push` now, before Step 1.
- If it says **`Your branch is up to date`** — go straight to Step 1.
- If it lists **modified files you have not committed**, commit them first:
  `git add -A && git commit -m "..."`, then `git push`.

This matters because the conflict list in Step 1 was verified against
`1e617a7`. If you have unpushed work you may see a slightly different list —
that is fine, but say what you actually see rather than forcing it to match.

## Step 1 · Merge the current `main` into your branch

```bash
git fetch origin
git merge origin/main
```

Git will stop and report **four** conflicts:

```
CONFLICT (content):  docs/build-log/STATUS.md
CONFLICT (add/add):  migrations/versions/022_platform_role.py
CONFLICT (content):  nidan/api/auth.py
CONFLICT (add/add):  nidan/infra/db/repositories/audit.py
```

Four, no more. If you see a different list, stop and ask before continuing.

## Step 2 · Take `main`'s version of all four

All four are files that were written, reviewed and merged on the other track.
Your versions are not worse — they are the same design — but there can only be
one, and `main`'s is what everything else is already built against.

```bash
git checkout --theirs docs/build-log/STATUS.md
git checkout --theirs migrations/versions/022_platform_role.py
git checkout --theirs nidan/api/auth.py
git checkout --theirs nidan/infra/db/repositories/audit.py
```

```bash
git add -A
git commit
```

Accept the default merge message.

**Your own work is untouched by this.** Everything below stays exactly as you
wrote it:

```
nidan/web/admin/__init__.py
nidan/web/admin/routes.py                  156 lines
nidan/web/templates/admin/base.html        259 lines
nidan/web/templates/admin/dashboard.html
nidan/web/templates/admin/cases.html
nidan/web/templates/admin/content.html
nidan/web/templates/admin/ops.html
nidan/web/templates/admin/reviews.html
nidan/web/templates/admin/system.html
nidan/web/templates/admin/users.html
nidan/app.py                               blueprint registration
tests/test_admin_auth.py                   175 lines
docs/build-log/T-020-admin-shell.md
```

`main`'s `auth.py` exports `current_actor`, `require_admin` and
`require_reviewer` — the three names your `routes.py` imports — so nothing
breaks. It also now has `current_admin()`, which T-021 needs; ignore it for now.

## Step 3 · Check it locally

```bash
source venv/bin/activate
ruff check .
pytest -m "not slow" -q
```

Then, with Docker Desktop running:

```bash
docker compose up -d db
pytest tests/db -q --no-cov
```

This last one is the check that was failing. It passes after the merge, because
`main`'s version of `tests/db/test_migrations.py` already knows `platform_role`
is the seventh enum type — yours predates that.

## Step 4 · Push

```bash
git push
```

The checks re-run on the same pull request. Do not open a new one.

---

# What actually broke, in one paragraph

You wrote `022_platform_role.py` because your brief told you to. The same
migration was then built on the other track and merged first. Your branch
therefore adds a seventh enum type to the database, but still carries the *old*
version of the test that asserts which enum types exist — a test `main` has
already updated. So the check failed with:

```
FAILED tests/db/test_migrations.py::test_all_six_enum_types_exist
Extra items in the left set: 'platform_role'
1 failed, 565 passed
```

One stale test. That is all it was.

**The duplication was a briefing mistake, not yours.** The first brief asked you
to build the migration; it was rebuilt on the other track and a revised brief
went out after you had already started. Your implementation matched on every
decision that mattered — an enum rather than a boolean, `404` never `403`, the
same reasoning written into the docstrings. That two people arrived at the same
design without coordinating says the spec is good.

**Your tests are being kept.** They are not duplicates. The ones on `main` test
the decorator and the audit repository in isolation; yours exercise the real
admin routes, including a parametrised test that every admin subpath 404s when
signed out. That covers something the others structurally cannot.

---

# Then read `00_START_HERE.md`

It has the workflow that stops this happening again — three commands at the
start of every task, and a list of files to leave alone.

The short version: **`git checkout main && git pull origin main` before you
branch, every single time.**
