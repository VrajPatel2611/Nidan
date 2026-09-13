# Command reference

Every command for this project, grouped by what you are trying to do.

Run everything from the project directory unless a command says otherwise:

```
cd ~/Desktop/A-bias-aware-vp-simulator
```

Getting the directory wrong is the single most common cause of a confusing
error. `docker compose up` from your home folder fails with *"no configuration
file found"*, not *"you are in the wrong place"*.

---

## 1 · First time on a new machine

```
git clone https://github.com/VrajPatel2611/A-bias-aware-vp-simulator.git
cd A-bias-aware-vp-simulator
```

**Create the virtual environment.** Python 3.11 or newer — the package refuses
to install on older versions, deliberately, because the code uses syntax they
cannot parse.

```
python3.11 -m venv venv
source venv/bin/activate
```

*Windows:* `py -3.11 -m venv venv` then `venv\Scripts\activate`

**Install the package and the development tools.**

```
pip install -e ".[dev]"
```

`-e` is *editable*: it puts a link to this folder on the Python path rather than
copying files, so an edit is live with no reinstall. `[dev]` adds pytest, ruff,
mypy and the rest — a production install does not ship them.

**Create your configuration.**

```
cp .env.example .env
```

Then open `.env` and paste your Groq key into `GROQ_API_KEY`. Free key from
https://console.groq.com

You can skip the key. The app starts, the case list works and the whole test
suite passes without one — only the patient's replies need it.

**Check it worked.**

```
pytest
```

555 tests, about 30 seconds — most of that is the database suite starting a
container. If they pass, the install is good.

---

## 2 · Running the app

**Day to day** — fastest, auto-reloads when you edit a file:

```
python -m nidan
```

Then open http://localhost:8000

**The full stack** — app plus PostgreSQL 16 with pgvector. Slower to start, and
what you want when the database work begins in T-010:

```
docker compose up --build
```

Same URL. Postgres is on `localhost:5433` on Vraj's machine, `localhost:5432`
elsewhere — see §7.

**Stop it:** `Ctrl+C`, or from another terminal:

```
docker compose down
```

**Stop it and wipe the database:**

```
docker compose down -v
```

The `-v` matters more than it looks. The scripts in `docker/postgres-init/` run
**once**, against an empty data directory. Edit them and nothing happens until
the volume is removed.

---

## 3 · Tests and quality

These are the six checks CI runs. Run them before you push and you will not be
surprised.

| Command | What it checks | Time |
|---|---|---|
| `pytest` | all 555 tests, plus the ≥90% coverage gate on `domain/` | ~30 s |
| `ruff check .` | style and common mistakes | <1 s |
| `ruff check . --fix` | the same, fixing what it can | <1 s |
| `mypy nidan/domain --strict` | types, on the domain layer only | ~5 s |
| `lint-imports` | the ADR-0009 layering contract | ~1 s |
| `pip-audit --skip-editable` | known vulnerabilities in dependencies | ~10 s |
| `python validate_detectors.py` | **detector accuracy — must stay ≥ 94%** | ~2 s |

### Running part of the suite

```
pytest -v
```
One line per test, with names.

```
pytest tests/domain/test_bias_anchoring.py
```
One file.

```
pytest -k anchoring
```
Every test whose name contains "anchoring".

```
pytest -x
```
Stop at the first failure.

```
pytest --lf
```
Re-run only what failed last time. Useful while fixing.

```
pytest tests/test_case_invariants.py -v --no-cov
```
The nine case invariants. `--no-cov` because running one file trips the coverage
gate, which is measured across the whole suite.

### The one that matters most

```
python validate_detectors.py
```

18 hand-labelled transcripts through the real detectors. It **exits non-zero
below 94%**, so CI fails the build.

If it fails, **do not lower the threshold.** The published paper reports 94%.
Find out what changed. The failure message says the same thing.

---

## 4 · Research tooling

```
python analyze_sessions.py sessions
```
Paired statistics — McNemar and Wilcoxon — over the session JSON files.

```
python test_api.py
```
Check the Groq key works. The quickest way to tell a key problem from a code
problem.

---

## 5 · Git

**Start a piece of work.** Never commit to `main` directly.

```
git checkout main && git pull && git checkout -b feature/short-description
```

**See what you have changed.**

```
git status
```

```
git diff
```

**Commit.**

```
git add -A && git commit -m "short description of what changed"
```

**Push and open a pull request.**

```
git push -u origin HEAD
```

Then open the PR on GitHub. CI runs automatically; all six jobs must pass.

**Undo, in increasing order of violence:**

```
git checkout -- path/to/file
```
Throw away changes to one file.

```
git stash
```
Set all changes aside. `git stash pop` brings them back.

```
git reset --hard
```
**Throws away every uncommitted change with no way back.** Be sure.

---

## 6 · Docker, in more detail

```
docker compose up --build
```
Build and start everything, logs in the terminal.

```
docker compose up -d --build
```
The same, in the background.

```
docker compose logs -f app
```
Follow the app's logs.

```
docker compose ps
```
What is running, and whether it is healthy.

```
docker compose exec db psql -U nidan -d nidan
```
A SQL prompt inside the database container. `\dx` lists extensions, `\q` quits.

```
docker compose build --no-cache
```
Rebuild from scratch. For when you suspect a stale layer.

---

## 6a · The database

Added by T-010 (schema) and T-012 (the repository layer). The schema lives in
`migrations/versions/` as 21 hand-written Alembic migrations — those files are
the source of truth, not any Python model.

```bash
docker compose up -d db
```

Start the database on its own. The app is not needed to run migrations or the
schema tests, and starting only `db` is quicker.

```bash
alembic upgrade head
```

Apply every migration in order. Needs `DATABASE_URL` set — `.env` is enough.
Running it twice is safe: Alembic records which revisions are applied.

```bash
alembic downgrade base
```

Tear the whole schema down. Every migration has a working `downgrade`, and
`tests/db/test_migrations.py` proves it by going down and back up.

```bash
alembic current
alembic history
```

Which revision the database is on, and the full list.

```bash
pytest tests/db -q --no-cov
```

180 tests against a real PostgreSQL 16 started in a container — constraints,
triggers, RLS policies, the seeded content, and the repository layer. Slower
than the rest of the suite because it starts a container and runs 20
migrations; skips rather than fails when Docker is not running.

```bash
docker compose exec db psql -U nidan -d nidan
```

A psql prompt inside the container. `\dt` lists tables, `\d sessions`
describes one, `\q` quits.

```bash
python scripts/backfill_pilot.py --dry-run
python scripts/backfill_pilot.py
```

Import the 16 pilot sessions into the schema (T-018). Run-once but idempotent —
every id is derived from the source data, so a second run updates the same rows
rather than creating a second copy of your pilot.

Run it **locally and in staging**. Whether the pilot belongs in the production
database is a privacy decision about real participants' data, not an engineering
one.

The imported results are the pilot's own numbers, stored under their own engine
version `pilot-2026-07` — never recomputed. Today's engine disagrees with one of
them, and that disagreement is the point: see
`docs/build-log/T-018-pilot-data-backfill.md`.

```bash
pip install -e ".[docs]"
python scripts/build_docx.py
python scripts/build_docx.py PRD BUILD_PLAN     # just those two
```

Regenerate the `.docx` copies of the documentation. **The Markdown is the source
of truth** — these exist because they are what gets shared with people who do
not read a repository: a mentor, a clinical reviewer, an examiner.

Run it after changing any document. Before this script they were produced by
hand, one at a time, which is why seven build logs had none and most of the rest
had drifted from the Markdown they were made from.

`python-docx` is an optional extra, not a dev dependency: CI has no reason to
install it, and a `.docx` is never a build artefact.

### Reading data as the application sees it

The application never issues a bare query. Everything goes through
`repo_scope(actor)`, which assumes a non-superuser role and sets `auth.uid()`
for the transaction (`ADR-0016`). In a REPL:

```python
from uuid import UUID
from nidan.infra.db.repositories import repo_scope, AuthenticatedUser

with repo_scope(AuthenticatedUser(UUID("..."))) as db:
    print(db.sessions.recent())
```

A psql prompt, by contrast, connects as the owner and is exempt from every
policy — which is exactly why it is useful for inspecting and useless for
checking isolation. To see what a *user* can see, use the scope.

---

## 7 · Things that go wrong, and the fix

### `zsh: command not found: docker`

Docker is not installed.

```
brew install --cask docker
```

Then **launch it** — installing gives you the command, not the running engine:

```
open -a Docker
```

Wait for the whale icon to stop animating, then check:

```
docker info
```

### `Cannot connect to the Docker daemon`

Docker Desktop is not running. `open -a Docker` and wait.

### `ports are not available: ... 5432: bind: address already in use`

Something else already uses PostgreSQL's port — on Vraj's Mac, Homebrew
`postgresql@15`. Fixed by adding this to `.env`:

```
POSTGRES_PORT=5433
```

The container then publishes on 5433. Nothing in the app changes: inside the
compose network the database is still `db:5432`.

To see what is holding a port:

```
lsof -nP -iTCP:5432 -sTCP:LISTEN
```

### `no configuration file found`

You are not in the project directory. `cd ~/Desktop/A-bias-aware-vp-simulator`

### `ERROR: Package 'nidan' requires a different Python: 3.9.6 not in '>=3.11'`

You are using the system Python instead of the virtual environment.

```
source venv/bin/activate
```

Or call the venv's interpreter directly: `venv/bin/python`, `venv/bin/pip`.

### `ModuleNotFoundError: No module named 'nidan'`

The package is not installed in the active environment.

```
pip install -e ".[dev]"
```

### Tests pass, then fail, with nothing changed

Stale compiled bytecode — usually after restoring a file with `cp`, which can
leave the source older than its cached `.pyc`.

```
find . -name __pycache__ -not -path "./venv/*" -exec rm -rf {} +
```

Restore files with `git checkout` rather than `cp` and this does not happen.

### `DATABASE_URL is not set, so no repository can open a transaction`

The repository layer refuses to build an engine without a URL rather than
failing later with a connection error. Start the database and make sure `.env`
has the line from `.env.example`:

```bash
docker compose up -d db
```

### `permission denied for table case_versions`

Working as intended. Migration 020 grants the application role `SELECT` on
clinical content and nothing else — cases change through the case editor after
a clinical review, never through a learner's request. If you genuinely need to
write content, use a `ServiceActor` and say why in its `reason`.

### An RLS test passes but you suspect it should not

Check what role the query actually ran as:

```python
db.conn.execute(sa.text("SELECT current_user")).scalar()
```

If that is anything but `nidan_app`, the policies were not applied — PostgreSQL
exempts superusers and the table owner from all of them. This is the single
most common way to get a green test that proves nothing, which is why
`test_the_scope_runs_as_nidan_app_which_cannot_bypass_rls` exists.

### `FAIL: detector accuracy 92.6% is below the required 94%`

A change degraded the detectors. **Do not lower the threshold.** Look at what
you changed in `nidan/domain/assessment/` or `nidan/domain/content/cases.py`.
`docs/detector_validation.md` shows which transcripts now fail.

### A case invariant fails (C-1 … C-9)

You edited a case and broke a rule. The message names the offending terms. The
fix is almost always to make the **anchor keyword more specific**, not to weaken
the clue — the clue vocabulary is what a learner naturally says when reasoning
correctly.

---

## 8 · The short version

Pin these five up somewhere:

```
source venv/bin/activate
python -m nidan
pytest
python validate_detectors.py
docker compose up --build
```

---

*Last updated 12 September 2026, after T-012.*
