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
| `python validate_personas.py` | **persona leakage — 80 real model calls** | ~2 min |

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

### Adding a clinical case

Author it in `nidan/domain/content/cases.py` — both layers, the stub in `CASES`
and the enrichment in `CLINICAL_DATA` — add a `CASE_SLUGS` entry, then:

```bash
pytest tests/test_case_invariants.py -q --no-cov
python scripts/generate_case_migration.py --revision 027 --down-revision 026 --cases case_8
alembic upgrade head
```

Invariants first. C-1 … C-9 only see cases that are in `CASES`, which is why
content is authored there rather than straight into the database — a case
written directly as JSON would skip every one of them, C-4 included.

**A new case is a new revision.** Never regenerate 019 or 026: the file would
still look generated and still import cleanly, and no database that already ran
them would ever see the change. The script refuses without `--force`.

### Adding a topic to the lexicon

Every case from 10 onwards needs new topics: cases 6 and 7 used the last of the
40 that migration 017 seeded. Add them to `TOPIC_KEYWORDS` in
`nidan/domain/assessment/topics.py`, then:

```bash
python scripts/generate_seed_migration.py --revision 029 --down-revision 028 \
  --name seed_topics_<what> --topics topic_one,topic_two
alembic upgrade head
```

The generated downgrade deletes **only the topics it added**. A table-wide
`DELETE FROM topic_lexicon` — which is what migration 017's downgrade does, and
can afford to, because it seeded everything there was — would take the other 40
with it, and nothing would fail at the time. Coverage scoring would just
silently credit nothing.

`tests/db/test_seed.py` compares the database against `TOPIC_KEYWORDS`, so a
topic added to the code with no migration fails there and nowhere else.

T-044 is the screen that would replace all of this. It is Phase 4.

### Giving someone the reviewer or admin role

```bash
python scripts/provision_reviewer.py --uid <supabase-user-uid> \
  --name "Dr Asha Nair" --timezone Asia/Kolkata --by <your-admin-uid>
```

Add `--dry-run` to see what it would do. The full procedure — creating the
account, assigning a case, checking it worked — is
`docs/process/REVIEWER_ONBOARDING.md`.

It replaces the two-statement `psql` in `LOCAL_ADMIN_ACCESS.md` §3, which is
fine for granting yourself admin on a laptop and wrong for onboarding a person:
that one writes to `auth.users` (Supabase's table, not ours), changes an
existing account's privilege without saying so, and records nothing. This
refuses all three and writes an `audit_log` row.

On a laptop there is no identity provider, so `--create-auth-user` inserts the
stub row as well. It refuses to do that unless it can prove the table is the
three-column stub from migration 001.

### Running the account jobs worker

```bash
python -m nidan.jobs status
python -m nidan.jobs run
```

`status` lists what is outstanding and does nothing. `run` processes every
pending step and exits — **idempotent, so running it twice is harmless**, and
that is a property of the queue rather than something the command arranges.

| Exit | Meaning |
|---|---|
| 0 | nothing pending, or everything attempted succeeded |
| 1 | at least one step failed — see the log, and `audit_log` for a `job.step_failed` row |
| 2 | bad usage |

A step that has failed 5 times is **stuck, not failed**, and does not set a
non-zero code: a permanently stuck job would otherwise make every scheduled
run report failure for ever, which is how a monitor gets switched off.
`status` is how you find those.

**What it does.** The outbound work behind the two 202s — building and
emailing a data export (`PRD` FR-11.3), and finishing an erasure: the
confirmation email, the payment provider, the Supabase credential
(`DATA_MODEL` §10.2, `UX_SPEC` S-20).

**Two things it will tell you it cannot do on a fresh checkout**, printed at
the top of every `run`:

```
email adapter : outbox   (EMAIL_FROM is not set)
billing       : none
supabase key  : NOT SET — the credential-deletion step cannot run
```

* **Nothing is delivered to an inbox.** `EMAIL_ADAPTER=outbox` is the only
  adapter built, and it writes each message to
  `logs/outbox/<timestamp>-<subject>-<id>/` as three files: `message.json`,
  `body.txt` and the attachment. Open them — that is the point. A real
  provider is a new class and a dict entry in
  `nidan/infra/email/__init__.py`; an unknown `EMAIL_ADAPTER` **raises**
  rather than falling back, so a deployment that asked for one cannot
  silently get a directory of files and believe it sent mail.
* **The credential is not deleted without `SUPABASE_SERVICE_ROLE_KEY`.** That
  key bypasses RLS entirely — `SECURITY_SPEC` §7.9 — so it belongs in this
  worker's environment and nowhere else. Without it the step refuses and
  records `job.step_failed` with `retryable: false`. It is **never** recorded
  as done, because that would make S-20's "within 24 h" silently false.

**There is no payment provider to cancel at.** Stripe is T-041, one phase
later, so the billing step records `no_provider_configured` rather than
claiming a cancellation it could not have made. `DATA_MODEL` §10.2's
transaction has already cancelled the subscription in the one place a
subscription exists.

**Scheduling it.** Nothing in the project schedules anything. On a laptop, run
it by hand, or add a cron line:

```bash
*/15 * * * * cd /path/to/Nidan && venv/bin/python -m nidan.jobs run >> logs/jobs.log 2>&1
```

Not a thread inside the API: the app runs on two gunicorn workers, so an
in-process scheduler would be two schedulers racing for the same jobs — and
`audit_log` rows cannot be claimed — and it would put the `service_role` key
into the process that serves public requests.

**Why `audit_log` is the queue.** It refuses UPDATE, including to the table
owner, and `ADR-0018` kept it that way because the record of an erasure must
not be editable by the thing performing one. So a job cannot be *marked*
done: it is done when its per-step completion rows exist, and
`AuditRepository.pending()` is the difference between the two sets. A crash
between a remote call and its completion row costs one retry rather than a
lost request.

### Bringing the whole demo up — one command

```bash
./scripts/demo_up.sh
```

Database, migrations, published cases, a warm LLM, the API, then the web app in
the foreground. Ctrl+C stops both servers. `--api-only` skips Next.js;
`--no-warm` skips the LLM call.

It is six checks and two servers rather than two servers, because **each of
these has broken a local run and none of them says what is wrong where you
notice it**:

| What it checks | What you see without the check |
|---|---|
| `.env` has `GROQ_API_KEY` | The patient answers 503 `patient_unavailable` |
| `.env` has `DATABASE_URL`, exported | `alembic` says "No database URL" — the app reads `.env` through pydantic-settings, `migrations/env.py` reads `os.getenv` only, so the two disagree about whether the database is configured |
| `web/.env.local` has all four values | `npm run dev` starts fine and fails on the sign-in screen |
| `nidan-db` is `healthy`, not merely up | Postgres accepts connections during initialisation and then restarts |
| `alembic upgrade head` | A schema one revision behind, failing somewhere that does not mention migrations |
| A published case exists | `POST /v1/sessions` → 503 `no_cases_available`, i.e. the Start button fails |
| One warm LLM call | The first question of the session takes ~2 minutes, not ~800 ms |
| Nothing else holds port 8000 | …and in particular: |

**The last one is the trap.** `docker-compose.yml`'s `app` service publishes
8000 and carries `restart: unless-stopped`, so it returns by itself after a
reboot — and **its image is baked at build time with no source mount.** Left
running, it both takes the port and serves whatever the code looked like when
it was last built. That is the worse failure of the two, because the demo
works: quietly, on old code. The script stops the container and says so, then
runs `python -m nidan` against the working tree.

The API's output goes to `logs/api.log`, the warm-up's to `logs/warm.log` and
alembic's to `logs/alembic.log` — interleaving two servers in one terminal
makes both unreadable. All three are covered by `.gitignore`'s `*.log`.

### Publishing cases on a laptop, so a demo can start one

```bash
python scripts/publish_for_demo.py --all --dry-run
python scripts/publish_for_demo.py --all
python scripts/publish_for_demo.py --all --undo
```

**The symptom this fixes reads like a bug and is not one.** Every case in the
bank is a `draft`, `SelectionRepository.candidates()` returns only published
versions, and so `POST /v1/sessions` answers `no_cases_available` (503) and the
web app cannot start a consultation. The test suite does not notice, because
its fixtures publish a case themselves — so the first place you meet this is a
demo.

It goes **through** migration 007's publish gate, not around it: it inserts an
approving `clinical_reviews` row with the full four-dimension rubric and then
flips the status, so the trigger still has to agree. Nothing disables a
trigger.

**It is not a clinical review and the data says so.** The row is attributed to
a profile called `Demo Fixture (not a clinician)` with a reserved UUID, and its
comment says it does not count towards the launch gate. That matters because
ten *clinician*-reviewed cases is the launch gate, and `clinical_reviews` is
the evidence for it.

**It refuses to run against anything but a local database** — `localhost`,
`127.0.0.1`, `::1`, `db` (the compose service name) or a Unix socket.
Fabricating an approval on the Supabase project would put a fake review
alongside the real ones. `tests/test_publish_for_demo.py` tests the refusal
rather than the publishing, including that a host merely *containing*
"localhost" is still refused.

`--undo` returns the versions to draft and deletes the fixture reviews,
draft-first so there is never a published version without an approving review.

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

Three real examples, all from writing cases 6 and 7 in October 2026:

| Broke | Why | Fix |
|---|---|---|
| anchor `tension` | inside `hyperTENSION`, which is the clue | `tension headache` |
| anchor `fever` | the clue is the *absence* of fever; it is the single most discriminating question in the case | removed from the anchor list |
| anchor `cold` | inside `cold air` and `cold weather` | `common cold` |

Each would have scored the question that solves the case as evidence of
fixating on the trap.

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


---

## The adversarial persona suite (T-040)

```bash
python validate_personas.py
```

Eight fixed extraction probes against each of the ten personas — 80 model
calls, so it costs money and takes a couple of minutes. It needs
`GROQ_API_KEY` and **no database**, so it works with the stack down.

```bash
python validate_personas.py --case case_3                 # one case
python validate_personas.py --probe greeting              # one probe
python validate_personas.py --json report.json            # full detail
```

**Run it after changing a model, and before any demo or reviewer session.**
`TECH_SPEC` §5.2 records that Groq retired `llama-3.3-70b-versatile` and it
took eleven weeks to notice; a different model has different leakage
behaviour, so a model change invalidates the tuning of all ten personas. The
CI job also runs weekly for the same reason — it is the one check whose result
can change with no commit at all.

**Exit codes.** `0` no persona named its own diagnosis or quoted its brief.
`1` one did — fix the persona's system prompt, do **not** weaken a probe. `3`
some probe never reached the provider, which is a failure on purpose: an
outage must not read as a clean bill of health.

**Do not pipe it.** `python validate_personas.py | tail -40` reports success
whatever the script returned, because the pipeline's status is `tail`'s. The
first exit-1 run was read as a pass that way. CI does not pipe, so the gate
itself is intact — but a local check that does is worse than no check.

**Fixing a leak means the shared brief, not the probe.** Both genuine leaks on
the first full run came from one probe (`what_to_order`) asking two personas
what tests to order, and both answered by naming the condition the test was
for. The fix was rule 6 in `_RULES` (`domain/content/cases.py`), which is the
brief **every** persona is built from — so after touching it, re-run this
suite *and* `python test_api.py`, which is the only check that goes through
the real gateway.

**Volunteering is measured, never gated.** The run prints the share of turns
whose reply offered required history the opening line had not already given.
It does not fail the build, and the reason is worth knowing: the patient model
runs at `temperature=0.7`, so volunteering is stochastic — the suite's first
two runs reported eight volunteering leaks and then **none**, from the same
probes against the same personas. `--repeat N` is how you measure it; CI uses
2. `TECH_SPEC` §5.3 defends volunteering with the runtime monitor and the
admin queue, and by reporting the rate.

```bash
python validate_personas.py --overlap
```

Pure — no model calls. Reports how much of each case's required history its
own opening line gives away. **Eight of the ten cases give away at least one
required topic, and `case_2` gives away four of eight.** That does not inflate
coverage (coverage is scored over `question` events and the opening line is
not one), but a learner who reads it and sensibly does not re-ask is scored as
having missed those topics. Not a gate: narrowing `required_topics` changes
the golden assessment record for all 16 pilot sessions.

---

## The research export (`DATA_MODEL` §11.7)

```bash
python scripts/research_export.py -o data.csv
```

The de-identified dataset: consent required, **sessions with a confirmed
persona-leakage flag excluded**, and `research_pid` as the only identifier —
no email, no `user_id`. `--json` for JSON instead of CSV; with no `-o` it
writes to stdout, and the summary goes to stderr so a redirect gives a clean
file.

It prints how many consented, completed sessions a confirmed flag removed.
**Report that figure as a limitation** — it is `TECH_SPEC` §5.3's third
defence against persona leakage, and the only one that is a writing habit
rather than code.

---

## The persona-leakage queue

`/admin/leakage`, under AI Ops. Each row is a reply that mentioned a required
topic its question did not ask about, with the patient's words beside it.

**Confirming a flag excludes that whole consultation from the research
export**, and it is audited as `leakage_flag.reviewed`. Dismissing leaves the
session in the dataset. Nothing is excluded until someone decides: a flag on
its own counts for nothing, whatever its severity.
