# Deploying the database to Supabase

**Read this before touching a production project.** It is written for the day
someone has to do it, not for today.

---

## 1 · The thing everyone expects, and why it is wrong

> *"Which file do I upload to Supabase so the database works?"*

**There is no file to upload.** Nothing in this repository is a database dump,
and pasting SQL into Supabase's editor is the wrong way to build this schema.

The schema is **21 ordered migrations** in `migrations/versions/`, applied by
Alembic against Supabase's PostgreSQL over a normal connection:

```bash
DATABASE_URL="<supabase connection string>" alembic upgrade head
```

That is the entire deployment. Supabase is just a hosted PostgreSQL; the
migrations do not know or care that it is Supabase.

**Why it has to be migrations and not a paste.** Alembic records which
revisions have run in an `alembic_version` table. That is what makes the next
deployment safe: it applies only what is new. A hand-pasted schema has no such
record, so the second change is a guess about what is already there. It also
loses the order, and order matters here — migration 016 writes policies that
reference a function migration 001 creates.

---

## 2 · Before you start

| | |
|---|---|
| **Region** | ⚠️ **Not yet decided** — `SECURITY_SPEC` S-4. One database, one jurisdiction. A global English-speaking launch (D-7) means UK and EU users, so this carries GDPR transfer obligations. **Decide deliberately; do not accept the default.** The region cannot be changed later without recreating the project |
| **Plan** | The free tier pauses after inactivity, which is fine for staging and not for production |
| **Postgres version** | 15 or later. The migrations use `make_interval`, partial indexes, and `GENERATED` defaults |

---

## 3 · Get the right connection string

Supabase offers three, and **they are not interchangeable**.

| Connection | Port | Use for migrations? |
|---|---|---|
| **Direct** | 5432 | ✅ **Yes** — use this |
| Session pooler | 5432 (pooler host) | ✅ Works |
| **Transaction pooler** | 6543 | ❌ **No** |

The transaction pooler does not support the prepared statements and
session-level state Alembic relies on, and migration 020's `SET ROLE` work and
the `DO $do$` blocks need a session that survives between statements. Using it
produces errors that look like schema problems and are not.

Find it in **Project Settings → Database → Connection string → URI**.

```bash
# Note the driver suffix. SQLAlchemy defaults postgresql:// to psycopg2,
# which is not a dependency here. The app normalises this automatically;
# Alembic on the command line does not.
export DATABASE_URL="postgresql+psycopg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres"
```

---

## 4 · Apply the schema

```bash
pip install -e .
alembic upgrade head
alembic current          # expect: 021 (head)
```

Roughly ten seconds. If it fails, it fails atomically — Alembic runs each
migration in a transaction, so a failure leaves the database on the previous
revision rather than half-migrated.

### What the migrations do that is Supabase-specific

Three of them are written to behave differently on a real project than on the
local container, and it is worth knowing which:

**Migration 001 — `auth.users` and `auth.uid()`.**
`profiles.id` references `auth.users(id)`, which **Supabase already provides**
and the application never writes to. Locally there is no such table, so 001
creates a minimal stub. On Supabase both guards make it a no-op:

- `CREATE TABLE IF NOT EXISTS auth.users` — yours is already there, and richer.
- `auth.uid()` is created **only if absent**, deliberately *not* with
  `CREATE OR REPLACE`. Overwriting Supabase's implementation with the local
  stub would be a security incident, not a convenience.

**Migration 001 — extensions.** `pgcrypto`, `citext`, `vector` (pgvector) and
`pg_trgm`. All four are available on Supabase. If `CREATE EXTENSION vector`
fails, enable it once in **Database → Extensions** and re-run.

**Migration 020 — the application roles.** Creates `nidan_app` (Row-Level
Security applies) and `nidan_service` (bypasses it), then grants both to
`CURRENT_USER`.

> **This is the one that matters most on Supabase.** The direct connection
> string authenticates as `postgres`, a **superuser** — and PostgreSQL exempts
> superusers from every RLS policy. If the application connected as `postgres`
> and did nothing else, all six policies would be silently inert while
> `pg_policies` still listed them.
>
> That is why every transaction opens with `SET LOCAL ROLE nidan_app`: it
> demotes the connection for the duration of the statement, so the policies
> apply even though the credentials are a superuser's. See `ADR-0016`.

---

## 5 · Verify it worked

Run these in Supabase's SQL editor. Each one has an expected answer.

```sql
-- 21 tables
SELECT count(*) FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- 9 RLS-enabled tables, every one with at least one policy.
-- Zero rows is the required answer: RLS enabled with NO policy denies
-- everything rather than allowing it, which is how four tables were
-- unreachable for three tasks (fixed in migration 021).
SELECT c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
LEFT JOIN pg_policy p ON p.polrelid = c.oid
WHERE c.relkind = 'r' AND c.relrowsecurity
GROUP BY c.relname HAVING count(p.polname) = 0;

-- Both roles exist, and only nidan_service bypasses RLS
SELECT rolname, rolbypassrls FROM pg_roles
WHERE rolname IN ('nidan_app', 'nidan_service');

-- Seeded content: 5 cases (status draft), 27 examinations,
-- 86 investigations, 40 topics, 1 current engine version
SELECT (SELECT count(*) FROM cases)               AS cases,
       (SELECT count(*) FROM examinations)        AS examinations,
       (SELECT count(*) FROM investigations)      AS investigations,
       (SELECT count(*) FROM engine_versions
         WHERE is_current)                        AS current_engine;
```

**The five cases arrive as `draft`, and that is correct.** `DATA_MODEL` §9.2:
publishing them without clinical review would make the publication gate a
formality. They stay drafts until a clinician approves them (T-023), which
means case selection will correctly return `no_cases_available` until then.

---

## 6 · Point the application at it

```bash
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
SUPABASE_URL=https://[REF].supabase.co
SUPABASE_JWT_AUDIENCE=authenticated
FLASK_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=production
GROQ_API_KEY=<your key>
```

**`FLASK_SECRET_KEY` is required in production and the app refuses to start
without it.** Each gunicorn worker imports the application separately, so
without a fixed key every worker signs session cookies with its own random
secret and rejects the others' — the learner is thrown out on roughly half
their requests, with nothing in the logs to explain it.

**Confirm the project issues asymmetric tokens.** Authentication verifies
RS256/ES256 against the JWKS endpoint. Older Supabase projects sign HS256 with
a shared secret, which this code deliberately refuses — accepting it would open
the algorithm-confusion attack.

---

## 7 · Do not do these

| | |
|---|---|
| **Do not paste the SQL by hand** | No `alembic_version` row means the next deployment cannot tell what has already run |
| **Do not edit an applied migration** | Write a new one. An edited migration is a schema that differs between environments with nothing to show it |
| **Do not use the transaction pooler (6543) for migrations** | §3 |
| **Do not run `alembic downgrade` against production** | It works, and it drops tables |
| **Do not grant the application role write access to `engine_versions` or clinical content** | It is read-only on both by design. `nidan_service` is the role the anonymous-trial path uses, so widening it widens that too |
| **Do not run `scripts/backfill_pilot.py` against production without deciding** | It imports 16 real participants' sessions. That is a privacy decision about people's data, not a deployment step. Locally and in staging: fine |

---

## 8 · If you have to start again

```bash
alembic downgrade base    # drops everything this repo created
alembic upgrade head
```

`downgrade base` is tested — `tests/db/test_migrations.py` goes down and back
up on every push, which is why it can be trusted. It does **not** touch
`auth.users` on Supabase; the guards in 001 only create, never drop.

---

## 9 · Related

| | |
|---|---|
| `DATA_MODEL.md` | The schema itself, table by table, and why |
| `ADR-0001` | Why PostgreSQL with pgvector, hosted on Supabase |
| `ADR-0016` | Why tenant scoping assumes a role per transaction |
| `SECURITY_SPEC.md` §S-4 | The region decision, still open |
| `COMMANDS.md` | Local database commands |
