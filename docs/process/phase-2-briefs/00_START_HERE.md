# Nidan · Phase 2 — read this first

You own **T-021, T-022, T-023**. Three tasks, ~11 days, all in `nidan/web/admin/`.

**First, finish T-020.** Your admin shell is written and pushed, but its pull
request is still red and unmerged. `FIX_T-020_FIRST.md` gets it green — about
ten minutes. Do that before you read the rest of this file, because T-021 builds
directly on T-020 being on `main`.

This file is the **process**: how to start a task, how to push it, and how to
open a pull request that goes green the first time. The other three files are
the **work**.

Read this one completely before you touch anything. It exists because T-020's
pull request went red, and every reason it went red is preventable.

---

# Part 1 — What went wrong on T-020, in one paragraph

You branched off `main` on 21 September. Between then and your push, a change
merged to `main` that added the same database migration you were writing, the
same `audit.py`, and the same `require_admin` / `require_reviewer` decorators.
Your code was fine — it was *correct*, and it matched the other version almost
line for line. But your branch was built on an **old copy of `main`**, so GitHub
saw two versions of several files, and a test that had already been updated on
`main` was still in its old form on your branch. That single stale test is what
turned the build red.

Nothing about that was a coding mistake. It was a **timing** mistake, and the
rules below remove the possibility of making it again.

---

# Part 2 — The five rules

### Rule 1 · Start every task from a fresh `main`

Never branch off your previous task's branch. Never keep working on a branch
after its pull request is merged. Every task starts from `main`, pulled fresh,
**on the day you start**.

### Rule 2 · One branch per task, named after the task

```
feat/t-021-case-editor
feat/t-022-playtest
feat/t-023-clinical-review
```

Not `admin`. Not `yogesh`. Not `new-branch`. The name tells the reviewer what is
inside before they open it.

### Rule 3 · Only write files this brief lists

Each task file has a **Files you write** table and a **Files you must not touch**
table. If a task seems to need a file from the second table, **stop and ask**.
Do not write it yourself, even if you know exactly how.

That rule is not about trust. It is the T-020 collision, stated as a rule.

### Rule 4 · Run the checks locally before you push

There are five. They take about four minutes together. Running them turns "the
build is red and I do not know why" into "I fixed it before anyone saw it."
Commands are in Part 5.

### Rule 5 · If `main` moved while you were working, merge it in before you push

Not after the pull request is open. Before. Commands are in Part 4.

---

# Part 3 · Setting up, once

```bash
# 1. Go to the project
cd path/to/Nidan

# 2. Make sure your clone points at the right place
git remote -v
# should print:  origin  https://github.com/VrajPatel2611/nidan.git  (fetch)
#                origin  https://github.com/VrajPatel2611/nidan.git  (push)
```

```bash
# 3. Python environment
python -m venv venv
source venv/bin/activate          # Windows:  venv\Scripts\activate
pip install -e ".[dev]"
```

```bash
# 4. Docker must be running for the database tests.
#    Start Docker Desktop, then:
docker compose up -d db
alembic upgrade head
```

```bash
# 5. Prove it all works before you write a line
pytest -q
```

That last command must end with `590 passed` or thereabouts. If it does not,
fix the setup **first** — do not start a task on a broken environment, because
then you cannot tell your failures apart from pre-existing ones.

`docs/process/WINDOWS_SETUP.md` covers the Windows-specific parts.

---

# Part 4 · The git workflow, start to finish

Follow this literally for each of the three tasks.

## 4.1 Starting a task

```bash
git checkout main
git pull origin main
git checkout -b feat/t-021-case-editor
```

Three commands, in that order, every time. The `git pull` is the one that
matters — it is the step whose absence caused the T-020 collision.

**Check you are actually up to date** before you start work:

```bash
git log --oneline -5
```

The newest commit should look recent and mention work you know about. If the
newest thing you see is from weeks ago, your `git pull` did not do what you
thought — run `git fetch origin && git status` and read what it says.

## 4.2 While you work — commit often

```bash
git add -A
git commit -m "feat(admin): sectioned case editor form (T-021)"
```

Small commits beat one enormous one. The message format the project uses is
`type(scope): what changed (T-0XX)`:

| Type | For |
|---|---|
| `feat` | new behaviour |
| `fix` | a bug |
| `test` | tests only |
| `docs` | documentation only |
| `refactor` | no behaviour change |

> **A commit is not a push.** `git commit` saves to your own machine only.
> Nobody — not GitHub, not your teammate, not CI — sees anything until
> `git push`. If you are ever unsure whether your work is safely on GitHub, run
> `git status`: if it says *"Your branch is ahead of 'origin/…' by N commits"*,
> it is still only on your laptop.

## 4.3 Before you push — the sync step

**Do this every time, even if you think nothing changed.**

```bash
git fetch origin
git log --oneline HEAD..origin/main
```

That second command lists commits that are on `main` but **not** on your branch.

**Outcome A — it prints nothing.** `main` has not moved. Skip to 4.4.

**Outcome B — it prints some commits.** `main` moved while you worked. Merge it
in now:

```bash
git merge origin/main
```

**B-1 · `Merge made by the 'ort' strategy`.** Good. Run the checks and push.

**B-2 · `CONFLICT`.** Git is telling you that you and `main` both changed the
same lines. Do not panic and do not delete anything. See what is conflicted:

```bash
git status
```

Then, for each conflicted file:

| Kind of file | What to do |
|---|---|
| A file in **your** "Files you write" table | Keep your version, but read `main`'s changes and fold them in by hand |
| A file in the **"must not touch"** table | Take `main`'s version wholesale: `git checkout --theirs <path>` |
| `docs/build-log/STATUS.md` | Take `main`'s version, then regenerate: `python scripts/build_status.py` |
| Anything you do not recognise | **Stop and ask.** Do not guess |

After resolving each file:

```bash
git add <path>
```

When `git status` shows no more conflicts:

```bash
git commit          # accept the default merge message
```

## 4.4 Run the checks

Part 5. All five. It is faster than a red build.

## 4.5 Push

First push of a branch:

```bash
git push -u origin feat/t-021-case-editor
```

Every push after that:

```bash
git push
```

## 4.6 Open the pull request

1. Go to **https://github.com/VrajPatel2611/nidan**
2. GitHub shows a yellow banner: *"feat/t-021-case-editor had recent pushes"* —
   click **Compare & pull request**. (If the banner is gone: **Pull requests →
   New pull request**.)
3. Check the two dropdowns at the top. They must read:
   **base: `main`** ← **compare: `feat/t-021-case-editor`**
   If `base` says anything other than `main`, change it. This is the single most
   common pull-request mistake.
4. Title: the same as your main commit message, e.g.
   `feat(admin): case editor with live C-4 validation (T-021)`
5. Description — answer these four, briefly:
   - What this adds
   - Which acceptance criteria from `BUILD_PLAN` it satisfies
   - Anything you deliberately left out
   - Anything you were unsure about
6. **Create pull request**
7. Scroll down and watch the checks. Eight jobs run. Wait for all of them.

**Nothing runs CI until the pull request exists.** `.github/workflows/ci.yml`
triggers on `pull_request` and on pushes to `main` — pushing a feature branch on
its own checks nothing.

## 4.7 When the checks go red

Do not push a "fix" blindly. Read the failure first.

1. Click **Details** next to the red job.
2. Scroll to the **bottom** of the log. The real error is almost always in the
   last 30 lines.
3. Find the line starting `FAILED` or `ERROR` and read the test's name.
4. Reproduce it locally — this is the important step:

```bash
pytest path/to/test_file.py::test_name -v
```

5. Fix, commit, push. The checks re-run automatically on the same pull request.
   You do **not** open a new one.

The eight jobs, and what a failure in each usually means:

| Job | Usually means |
|---|---|
| **Lint and types** | `ruff check . --fix` will fix most of it |
| **Tests** | a real test failure — reproduce locally |
| **Tests (Windows)** | almost always a file-path or encoding difference |
| **Database schema** | migrations, constraints, RLS. **If you did not write a migration, this failing means your branch is stale — go back to 4.3** |
| **Detector validation** | you changed something in `domain/assessment/`. You should not have |
| **Case content invariants** | a case in `domain/content/cases.py` broke C-1…C-9 |
| **Security** | a dependency CVE, or a secret got committed. Never commit a `.env` |
| **Docker image builds** | the `Dockerfile` cannot build |

**"Database schema" failing when you wrote no migration is the T-020 signature.**
It means `main` has schema changes your branch does not. Merge `main` in.

## 4.8 After it merges

```bash
git checkout main
git pull origin main
git branch -d feat/t-021-case-editor
```

Then start the next task from 4.1. Never reuse a merged branch.

---

# Part 5 · The five checks, before every push

Run them in this order. Stop at the first failure and fix it.

```bash
source venv/bin/activate
```

```bash
# 1 — style and types  (CI job: "Lint and types")
ruff check . --fix && mypy nidan/domain --strict && lint-imports
```

```bash
# 2 — the test suite  (CI job: "Tests")
pytest -m "not slow" -q
```

```bash
# 3 — database tests  (CI job: "Database schema")  — needs Docker running
docker compose up -d db
pytest tests/db -q --no-cov
```

```bash
# 4 — the research claim  (CI job: "Detector validation")
python validate_detectors.py
```

```bash
# 5 — case content  (CI job: "Case content invariants")
pytest tests/test_case_invariants.py -q --no-cov
```

If all five pass, your pull request will be green. If check 3 is skipped because
Docker is not running, **that is not a pass** — start Docker and run it
properly, because CI will.

---

# Part 6 · Who owns which files

The layering rule (`ADR-0009`) is not a style preference; it is enforced by
`lint-imports` and will fail your build.

```
nidan/domain/     pure logic. Never imports infra/ or api/.        not yours
nidan/infra/      database, LLM, auth.                             not yours
nidan/api/        Flask routes and decorators.                     not yours
nidan/web/        templates, static, admin console.                YOU
migrations/       the database schema.                             not yours
```

### Yours across all of Phase 2

```
nidan/web/admin/**
nidan/web/templates/admin/**
nidan/web/static/admin/**
tests/test_admin_*.py
docs/build-log/T-0XX-*.md      (one per task, yours to write)
```

### Never, in any task

```
migrations/**                       ← this is the one that caused T-020
nidan/domain/**
nidan/infra/**
nidan/api/auth.py
nidan/api/v1.py
docs/spec/**                        ← except the one STATUS line, see below
```

The **only** exception: when a task is finished you tick its line in
`docs/spec/BUILD_PLAN.md` and run `python scripts/build_status.py`. That is a
one-line change, and if it conflicts you take `main`'s version and regenerate.

**If a task looks like it needs a file from the "never" list, that is real
information, not a blocker to work around.** Say what you need and start on a
part of the task that does not need it. T-021 had exactly one such dependency
and it has already been built for you.

---

# Part 7 · Rules of the product that are easy to break

These are not style. Breaking one fails a test or, worse, quietly damages the
research instrument. The full list is in `CLAUDE.md` at the repository root —
these are the ones your tasks touch.

**The admin console refuses with 404, never 403.** No token, expired token,
signed in without privilege — all return an identical 404 body. A 403 tells a
stranger that an admin console exists, and a *difference* between the refusals
is the same leak more quietly. Your T-020 code already does this; keep doing it.

**Every admin action writes to `audit_log`.** Use `db.audit.record(...)`. The
actor comes from the request scope — you never pass it in.

**Never open a database connection outside `infra/db`.** Every query goes
through `with repo_scope(...) as db:`. A connection obtained any other way runs
with row-level security switched off and looks completely normal.

**The actor decides the privilege.** `current_actor()` for reads,
`current_admin()` for anything that writes clinical content. T-021 explains why.

**Never use bias vocabulary in user-facing text.** Not "bias", "anchoring",
"premature closure", "confirmation bias". The screens a clinician reads use
plain language.

**Never touch anything under `domain/assessment/`.** It is the research
instrument. The "Detector validation" CI job exists to catch exactly that.

**British English** in anything a person reads.

---

# Part 8 · Where to look things up

Read only what you need. The specs total around 40 000 words.

| Question | File |
|---|---|
| What is this project? | `CLAUDE.md` |
| What is every file in here? | `docs/PROJECT_MAP.md` |
| What exactly must T-0XX do? | `docs/spec/BUILD_PLAN.md`, find the task block |
| What does the screen look like? | `docs/spec/UX_SPEC.md` §12 |
| What shape is the data? | `docs/spec/DATA_MODEL.md` §8 |
| Why was X decided? | `docs/spec/adr/` — 16 one-page records |
| What command was that? | `docs/process/COMMANDS.md` |
| What is already done? | `docs/build-log/STATUS.md` |

**Check `docs/spec/adr/` before re-arguing a decision.** Most "why is it done
this strange way" questions have a one-page answer there.

---

# Part 9 · The order, and the one thing to know about it

```
T-021  Case editor         5 d
T-022  Playtest            4 d
T-023  Clinical review     2 d   ← the one that matters most
```

Strictly in that order — each genuinely depends on the one before.

**T-023 is the gate for the whole project.** Until it exists, the two clinician
reviewers cannot look at a case at all, no case can be published, and content
authoring — which is the real critical path to launch, more than any
engineering — cannot start. The five remaining cases are blocked behind your
2-day task.

That is worth knowing while you are working on the two tasks in front of it.
