# Nidan — Data Model

---

## Contents

**1. Document control**

&nbsp;&nbsp;&nbsp;&nbsp;1.1 The rule that matters most  
&nbsp;&nbsp;&nbsp;&nbsp;1.2 Scope  
**2. Conventions**

&nbsp;&nbsp;&nbsp;&nbsp;2.1 Keys  
&nbsp;&nbsp;&nbsp;&nbsp;2.2 Timestamps  
&nbsp;&nbsp;&nbsp;&nbsp;2.3 Deletion  
&nbsp;&nbsp;&nbsp;&nbsp;2.4 Naming  
&nbsp;&nbsp;&nbsp;&nbsp;2.5 Nullability  
&nbsp;&nbsp;&nbsp;&nbsp;2.6 Enums versus check constraints  
&nbsp;&nbsp;&nbsp;&nbsp;2.7 Standard triggers  
&nbsp;&nbsp;&nbsp;&nbsp;2.8 Required extensions  
**3. Entity relationship overview**

**4. Identity and commerce**

&nbsp;&nbsp;&nbsp;&nbsp;4.1 `profiles`  
&nbsp;&nbsp;&nbsp;&nbsp;4.2 `subscriptions`  
&nbsp;&nbsp;&nbsp;&nbsp;4.3 `user_progress`  
&nbsp;&nbsp;&nbsp;&nbsp;4.4 `user_case_history`  
**5. Clinical content**

&nbsp;&nbsp;&nbsp;&nbsp;5.1 `cases` and `case_versions`  
&nbsp;&nbsp;&nbsp;&nbsp;5.2 `clinical_reviews`  
&nbsp;&nbsp;&nbsp;&nbsp;5.3 `examinations` and `investigations`  
&nbsp;&nbsp;&nbsp;&nbsp;5.4 `topic_lexicon` and `topic_phrases`  
**6. Sessions — the core**

&nbsp;&nbsp;&nbsp;&nbsp;6.1 `sessions`  
&nbsp;&nbsp;&nbsp;&nbsp;6.2 `session_events` — append-only  
&nbsp;&nbsp;&nbsp;&nbsp;6.3 `session_results` — derived  
&nbsp;&nbsp;&nbsp;&nbsp;6.4 `engine_versions`  
&nbsp;&nbsp;&nbsp;&nbsp;6.5 `feedback_texts`  
**7. Operations**

&nbsp;&nbsp;&nbsp;&nbsp;7.1 `llm_calls`  
&nbsp;&nbsp;&nbsp;&nbsp;7.2 `leakage_flags`  
&nbsp;&nbsp;&nbsp;&nbsp;7.3 `idempotency_keys`  
&nbsp;&nbsp;&nbsp;&nbsp;7.4 `audit_log`  
&nbsp;&nbsp;&nbsp;&nbsp;7.5 `feature_flags`  
**8. JSONB schemas**

&nbsp;&nbsp;&nbsp;&nbsp;8.1 `case_versions.content`  
&nbsp;&nbsp;&nbsp;&nbsp;8.2 `session_events.payload`  
&nbsp;&nbsp;&nbsp;&nbsp;8.3 `user_progress.bias_trends`  
&nbsp;&nbsp;&nbsp;&nbsp;8.4 `clinical_reviews.scores`  
&nbsp;&nbsp;&nbsp;&nbsp;8.5 `session_results.bias_detail`  
&nbsp;&nbsp;&nbsp;&nbsp;8.6 Scorecard JSONB  
&nbsp;&nbsp;&nbsp;&nbsp;8.7 `engine_versions.thresholds`  
**9. Migrations and seed**

&nbsp;&nbsp;&nbsp;&nbsp;9.1 Migration sequence  
&nbsp;&nbsp;&nbsp;&nbsp;9.2 Seed data  
&nbsp;&nbsp;&nbsp;&nbsp;9.3 Migrating the 16 pilot sessions  
&nbsp;&nbsp;&nbsp;&nbsp;9.4 Zero-downtime rules  
**10. Security and privacy**

&nbsp;&nbsp;&nbsp;&nbsp;10.1 Row-Level Security  
&nbsp;&nbsp;&nbsp;&nbsp;10.2 Deletion and erasure  
&nbsp;&nbsp;&nbsp;&nbsp;10.3 Retention  
**11. Query patterns**

&nbsp;&nbsp;&nbsp;&nbsp;11.1 Case selection (`PRD` FR-3.1)  
&nbsp;&nbsp;&nbsp;&nbsp;11.2 Free-tier allowance (`PRD` FR-10.1)  
&nbsp;&nbsp;&nbsp;&nbsp;11.3 Session reconstruction (`ADR-0003`)  
&nbsp;&nbsp;&nbsp;&nbsp;11.4 Subscription drift reconciliation  
&nbsp;&nbsp;&nbsp;&nbsp;11.5 Rebuild `user_progress`  
&nbsp;&nbsp;&nbsp;&nbsp;11.6 Case difficulty (anti-answer-sharing, `ADR-0014`)  
&nbsp;&nbsp;&nbsp;&nbsp;11.7 Research export (de-identified)  
&nbsp;&nbsp;&nbsp;&nbsp;11.8 LLM cost per completed session  
**12. Forward declarations**

**13. Open questions**


---

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan Data Model |
| **Version** | v1.0 |
| **Status** | Draft |
| **Database** | PostgreSQL 16 + `pgvector`, hosted on Supabase (`ADR-0001`) |
| **Depends on** | `PRD.md` §6, §9 · `ADR-0001`, `ADR-0003`, `ADR-0010`, `ADR-0015` |

## 1.1 The rule that matters most

> **This document changes in the same commit as the migration.** A schema change without a matching edit here is an incomplete change and should fail review.

If the document and the database can drift, they will, and a stale schema document is worse than none — people trust it and are wrong.

## 1.2 Scope

Covers every table required for v1 (`PRD` §5.1). Tables required only by deferred features (Case Factory, research studies, institutional cohorts) appear in §12 as forward declarations — **not created in v1**, but designed now so adding them later needs no restructuring.

---

# 2. Conventions

Applied without exception. Deviations require a note in the table spec explaining why.

## 2.1 Keys

| Rule | Detail |
|---|---|
| Primary keys | `UUID` with `DEFAULT gen_random_uuid()` for all domain entities |
| Exception | High-volume append-only logs use `BIGSERIAL` — `session_events`, `audit_log`, `llm_calls`. Sequential integers are smaller, index better, and these are never exposed in URLs |
| Foreign keys | Always declared. Always with an explicit `ON DELETE` action |
| Natural keys | Never used as primary keys. `slug`, `key` and similar get a `UNIQUE` constraint instead |

**Why UUID for domain entities:** identifiers appear in URLs (`/case/{sessionId}`). Sequential integers leak volume — a competitor can read your session count from a URL — and permit enumeration attacks.

## 2.2 Timestamps

| Rule | Detail |
|---|---|
| Type | `TIMESTAMPTZ` always. **Never `TIMESTAMP`** |
| `created_at` | On every table. `NOT NULL DEFAULT now()` |
| `updated_at` | Only on mutable tables, maintained by trigger (§2.7) |
| Business times | Named explicitly: `started_at`, `ended_at`, `published_at`, `reviewed_at` |
| Storage | UTC. Timezone conversion is a presentation concern |

**Exception — streaks.** `user_progress.last_session_date` is a `DATE` in the user's local timezone, stored alongside `timezone`. A streak is a human calendar concept; computing it in UTC breaks for users far from GMT (`PRD` FR-9.6).

## 2.3 Deletion

| Data | Strategy |
|---|---|
| `profiles` | Soft delete — `deleted_at` set, identifying fields nulled (§10.2) |
| `cases`, `case_versions` | Never deleted. Status moves to `retired` |
| `examinations`, `investigations` | Never deleted. `is_active = false` |
| `sessions`, `session_events`, `session_results` | Never deleted directly; cascade from profile hard-deletion only after anonymisation |
| Everything else | Hard delete acceptable |

## 2.4 Naming

`snake_case` · plural tables (`sessions`) · singular columns · booleans read as assertions (`is_active`, `consent_research`) · foreign keys are `{singular_table}_id` · enums are singular (`session_status`).

## 2.5 Nullability

**Columns are `NOT NULL` unless nullability carries meaning.** A nullable column must have a documented interpretation of `NULL` in its table spec.

Legitimate examples: `sessions.ended_at` (null = still running), `profiles.institution_id` (null = individual user), `case_versions.published_at` (null = not published).

## 2.6 Enums versus check constraints

| Use | When |
|---|---|
| **Postgres `ENUM`** | Closed, stable sets that appear in application logic — `session_status`, `user_role` |
| **`TEXT` + `CHECK`** | Sets likely to grow — `subscriptions.provider`, `subscriptions.status` |

**Rationale:** adding an enum value requires `ALTER TYPE`, which cannot run inside a transaction with other DDL in some versions. For values expected to grow, a check constraint is cheaper to change.

## 2.7 Standard triggers

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
-- Applied to every table carrying updated_at.

CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'Table % is append-only', TG_TABLE_NAME; END;
$$ LANGUAGE plpgsql;
-- Applied as BEFORE UPDATE OR DELETE on session_events and audit_log.
```

The append-only guarantee (`ADR-0003`) is enforced in the database, not only in application code.

## 2.8 Required extensions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;      -- case-insensitive email
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector, embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy search in admin
```

---

# 3. Entity relationship overview

```
auth.users (Supabase)
     │ 1:1
     ▼
  profiles ─────┬──< sessions ──┬──< session_events        (append-only)
     │          │               ├─── session_results       (1:1, derived)
     │          │               └──< feedback_texts
     │          │                        │
     │          │                        └──< llm_calls
     │          │
     │          ├──< user_case_history >── cases
     │          ├─── user_progress  (1:1)
     │          └──< subscriptions
     │
     └──< clinical_reviews >── case_versions >── cases
                                    │
                              engine_versions ──< session_results

  examinations   (master list, referenced by key)
  investigations (master list, referenced by key)
  topic_lexicon ──< topic_phrases
  audit_log · feature_flags · idempotency_keys · leakage_flags
```

**19 tables in v1.**

---

# 4. Identity and commerce

## 4.1 `profiles`

Extends Supabase's `auth.users` 1:1. We never write to `auth.users`.

```sql
CREATE TYPE professional_role AS ENUM
    ('medical_student','intern','resident','physician','other');

CREATE TYPE subscription_tier AS ENUM ('free','pro');

-- Platform privilege (T-020). Distinct from professional_role: a physician is
-- not an admin. An enum rather than a boolean because clinical_reviews
-- .reviewer_id already implies a second privileged kind — T-023 has reviewers
-- opening a case version in Playtest, so they reach the console too.
CREATE TYPE platform_role AS ENUM ('user','reviewer','admin');

CREATE TABLE profiles (
    id                  UUID PRIMARY KEY
                        REFERENCES auth.users(id) ON DELETE CASCADE,

    display_name        TEXT,
    professional_role   professional_role,
    year_of_training    SMALLINT CHECK (year_of_training BETWEEN 1 AND 10),
    country             CHAR(2),                     -- ISO 3166-1 alpha-2
    timezone            TEXT NOT NULL DEFAULT 'UTC', -- IANA, e.g. 'Asia/Kolkata'

    -- Pseudonymous identifier. Used in every analytics and research export.
    -- Never appears alongside email in the same query result.
    research_pid        TEXT NOT NULL UNIQUE
                        DEFAULT ('U' || upper(substr(replace(gen_random_uuid()::text,'-',''),1,10))),

    platform_role       platform_role NOT NULL DEFAULT 'user',
    subscription_tier   subscription_tier NOT NULL DEFAULT 'free',
    subscription_ends   TIMESTAMPTZ,

    -- Nullable: individual users have no institution (ADR-0015).
    institution_id      UUID,

    onboarded_at        TIMESTAMPTZ,
    last_active_at      TIMESTAMPTZ,

    consent_research    BOOLEAN NOT NULL DEFAULT false,
    consent_version     TEXT,
    consent_at          TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT consent_recorded_together
        CHECK ((consent_research = false) OR
               (consent_version IS NOT NULL AND consent_at IS NOT NULL))
);

CREATE INDEX ON profiles (subscription_tier) WHERE deleted_at IS NULL;

-- Partial: almost every row is 'user', so an index over them would be a scan
-- of the table wearing an index's clothes. The only question asked of this
-- column is "who is privileged".
CREATE INDEX profiles_privileged ON profiles (platform_role)
    WHERE platform_role <> 'user';
CREATE INDEX ON profiles (last_active_at DESC) WHERE deleted_at IS NULL;
```

| Column | Null means |
|---|---|
| `display_name` | Never set; UI falls back to email local-part |
| `professional_role`, `year_of_training` | Onboarding skipped (`PRD` FR-2.7) |
| `subscription_ends` | Free tier, or a lifetime grant |
| `institution_id` | Individual user — the normal case in v1 |
| `onboarded_at` | Onboarding not completed |
| `deleted_at` | Active account |

**`research_pid` is a stored column, not derived.** It must survive profile anonymisation so published analyses remain reproducible after a user exercises their right to erasure (§10.2).

**Sample row**

| id | research_pid | role | year | tier | tz |
|---|---|---|---|---|---|
| `9f3a…` | `U4B7C21E9AF` | `medical_student` | 4 | `free` | `Asia/Kolkata` |

## 4.2 `subscriptions`

```sql
CREATE TABLE subscriptions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,

    provider              TEXT NOT NULL
                          CHECK (provider IN ('stripe','apple','google','manual')),
    provider_customer_id  TEXT,
    provider_sub_id       TEXT,

    tier                  subscription_tier NOT NULL,
    status                TEXT NOT NULL
                          CHECK (status IN ('active','past_due','cancelled','expired','trialing')),
    interval              TEXT CHECK (interval IN ('month','year')),

    currency              CHAR(3),
    amount_minor          INTEGER,     -- smallest currency unit; avoids float
    country               CHAR(2),     -- for regional pricing analysis

    current_period_start  TIMESTAMPTZ,
    current_period_end    TIMESTAMPTZ,
    cancel_at_period_end  BOOLEAN NOT NULL DEFAULT false,
    grace_until           TIMESTAMPTZ,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (provider, provider_sub_id)
);

CREATE INDEX ON subscriptions (user_id, status);
CREATE UNIQUE INDEX one_active_sub_per_user
    ON subscriptions (user_id) WHERE status IN ('active','trialing','past_due');
```

**`amount_minor` as an integer, never a float.** ₹499 is stored as `49900`. Floating-point currency produces rounding errors that surface in reconciliation.

**The partial unique index prevents double-billing** — a user cannot hold two live subscriptions, which is the failure mode when a webhook is processed twice or a user checks out in two tabs.

**`profiles.subscription_tier` is denormalised** from this table. It is read on nearly every request for gating; a join per request is wasteful. It is updated in the same transaction as the subscription row, and §11.4 has a reconciliation query to detect drift.

## 4.3 `user_progress`

One row per user, maintained incrementally.

```sql
CREATE TABLE user_progress (
    user_id              UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,

    sessions_completed   INTEGER NOT NULL DEFAULT 0,
    current_streak_days  INTEGER NOT NULL DEFAULT 0,
    longest_streak_days  INTEGER NOT NULL DEFAULT 0,
    last_session_date    DATE,          -- in the user's timezone, see §2.2

    -- Rolling window over the last 10 completed sessions.
    -- {"anchoring":{"last10":0.2,"prev10":0.5},...}  — shape in §8.3
    bias_trends          JSONB NOT NULL DEFAULT '{}'::jsonb,
    mean_coverage_last10 NUMERIC(5,2),

    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Why a materialised table rather than computing on read:** the dashboard (`S-08`) loads on nearly every visit and needs these four numbers. Recomputing a streak across all sessions on every page load is wasteful. Updated in the same transaction that completes a session; §11.5 has a rebuild query if it ever drifts.

## 4.4 `user_case_history`

```sql
CREATE TABLE user_case_history (
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    case_id         UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    times_attempted INTEGER NOT NULL DEFAULT 1,
    first_attempt   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt    TIMESTAMPTZ NOT NULL DEFAULT now(),
    best_verdict    TEXT,
    PRIMARY KEY (user_id, case_id)
);
```

Exists to serve `PRD` FR-3.1 — never offer a case the user has already completed until the others are exhausted. Keyed on `case_id`, not `case_version_id`: a user who saw v1 of a case should not be served v2 as though it were new.

---

# 5. Clinical content

## 5.1 `cases` and `case_versions`

Identity is separated from content so sessions can pin immutable content (`ADR-0010`).

```sql
CREATE TYPE case_status AS ENUM ('draft','in_review','published','retired');
CREATE TYPE case_origin AS ENUM ('hand_authored','generated');

CREATE TABLE cases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,       -- 'chest-pain-gerd'
    specialty   TEXT,
    origin      case_origin NOT NULL DEFAULT 'hand_authored',
    created_by  UUID REFERENCES profiles(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE case_versions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id              UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    version              INTEGER NOT NULL,
    status               case_status NOT NULL DEFAULT 'draft',

    -- Full case payload. Schema in §8.1.
    content              JSONB NOT NULL,

    -- Denormalised from content for querying without JSON extraction.
    title                TEXT NOT NULL,
    anchor_topic         TEXT NOT NULL,
    minimum_questions    SMALLINT NOT NULL CHECK (minimum_questions BETWEEN 3 AND 20),
    required_topic_count SMALLINT NOT NULL,
    key_investigation_count SMALLINT NOT NULL,

    content_hash         TEXT NOT NULL,          -- sha256 of canonical content
    embedding            vector(384),            -- near-duplicate detection

    -- Provenance (populated only for generated cases)
    source_dataset       TEXT,
    source_record_id     TEXT,
    qa_report            JSONB,
    trap_selftest_passed BOOLEAN,

    published_at         TIMESTAMPTZ,
    retired_at           TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (case_id, version),

    CONSTRAINT published_requires_timestamp
        CHECK (status <> 'published' OR published_at IS NOT NULL)
);

CREATE UNIQUE INDEX one_published_version_per_case
    ON case_versions (case_id) WHERE status = 'published';

CREATE INDEX published_cases
    ON case_versions (id) WHERE status = 'published';

CREATE INDEX ON case_versions USING hnsw (embedding vector_cosine_ops);
```

**`one_published_version_per_case` is important.** Without it, two versions could be live simultaneously and case selection would be non-deterministic.

**Denormalised columns** (`title`, `minimum_questions`, `key_investigation_count`) exist because the admin case bank (`A-01`) and case selection both filter and sort on them. Extracting from JSONB on every query is slow and cannot be indexed usefully. They are written by the application from `content` and verified by a check in CI.

### The publication gate

```sql
-- Enforces PRD FR-12.5: no case reaches a user without clinical sign-off.
CREATE OR REPLACE FUNCTION require_clinical_approval() RETURNS trigger AS $$
BEGIN
  IF NEW.status = 'published' AND OLD.status <> 'published' THEN
    IF NOT EXISTS (
      SELECT 1 FROM clinical_reviews
      WHERE case_version_id = NEW.id AND decision = 'approved'
    ) THEN
      RAISE EXCEPTION 'Case version % has no approving clinical review', NEW.id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_clinical_approval
  BEFORE UPDATE ON case_versions
  FOR EACH ROW EXECUTE FUNCTION require_clinical_approval();
```

**This is a product requirement enforced in the database.** Application-level checks can be bypassed by a migration script, an admin console bug, or a direct SQL fix at 2am. This cannot.

## 5.2 `clinical_reviews`

```sql
CREATE TABLE clinical_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_version_id UUID NOT NULL REFERENCES case_versions(id) ON DELETE CASCADE,
    reviewer_id     UUID NOT NULL REFERENCES profiles(id),

    decision        TEXT NOT NULL
                    CHECK (decision IN ('approved','changes_requested','rejected')),

    -- Structured rubric, 1-5 each. Shape in §8.4.
    scores          JSONB NOT NULL,
    comments        TEXT,

    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON clinical_reviews (case_version_id, reviewed_at DESC);
CREATE INDEX ON clinical_reviews (reviewer_id, reviewed_at DESC);
```

Reviews are **append-only in practice** — a reviewer changing their mind adds a new row. The trigger above checks for *any* approving review, so the review history is preserved.

## 5.3 `examinations` and `investigations`

The master lists, moved out of `cases.py` so the admin console can edit them (`PRD` FR-12.7).

```sql
CREATE TABLE examinations (
    key            TEXT PRIMARY KEY,        -- 'vitals'  — immutable once used
    label          TEXT NOT NULL,
    group_name     TEXT NOT NULL,
    normal_result  TEXT NOT NULL,
    display_order  SMALLINT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investigations (
    key             TEXT PRIMARY KEY,       -- 'ecg'
    label           TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    normal_result   TEXT NOT NULL,
    reference_range TEXT,
    display_order   SMALLINT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON examinations (group_name, display_order) WHERE is_active;
CREATE INDEX ON investigations (group_name, display_order) WHERE is_active;
```

**`key` is a `TEXT` primary key, deliberately.** These keys appear inside `case_versions.content` JSON and inside `session_events.payload`. A surrogate UUID would make that JSON unreadable and every debugging session harder. The keys are stable, short, and human-meaningful.

**Deletion is forbidden**, not merely discouraged — a key referenced by a published case must remain resolvable forever, because sessions store the key. `is_active = false` removes it from the menu without breaking history.

**v1 seeds:** 27 examinations, 86 investigations (§9.2).

## 5.4 `topic_lexicon` and `topic_phrases`

```sql
CREATE TABLE topic_lexicon (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_key     TEXT NOT NULL UNIQUE,     -- 'meal_relationship'
    display_name  TEXT NOT NULL,            -- 'Relationship to meals'
    description   TEXT,                     -- canonical sentence, embedded later
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE topic_phrases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id        UUID NOT NULL REFERENCES topic_lexicon(id) ON DELETE CASCADE,
    phrase          TEXT NOT NULL,
    embedding       vector(384),            -- null until ADR-0013 phase 2

    -- Populated by a nightly job. Drives the dead-phrase report (UX A-06).
    match_count     INTEGER NOT NULL DEFAULT 0,
    last_matched_at TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic_id, phrase)
);

CREATE INDEX ON topic_phrases USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON topic_phrases (topic_id);
```

**v1 seed:** 40 topics, 523 phrases, `embedding` null throughout. Populating embeddings is Phase 5 work (`ADR-0013`); the column exists now so adding them is a backfill rather than a migration.

**`match_count` supports a real operational need:** a phrase that has never matched in 90 days is noise in the lexicon, and the admin console surfaces those for removal.

---

# 6. Sessions — the core

## 6.1 `sessions`

```sql
CREATE TYPE session_status AS ENUM ('active','completed','abandoned','expired');

CREATE TABLE sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Exactly one of these is set. Anonymous trial sessions (PRD FR-2) have
    -- anonymous_id; on signup the session is claimed and user_id is populated.
    user_id           UUID REFERENCES profiles(id) ON DELETE CASCADE,
    anonymous_id      TEXT,

    case_version_id   UUID NOT NULL REFERENCES case_versions(id) ON DELETE RESTRICT,

    sequence_index    INTEGER NOT NULL,
    status            session_status NOT NULL DEFAULT 'active',

    confidence_pre    SMALLINT CHECK (confidence_pre BETWEEN 1 AND 5),

    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at          TIMESTAMPTZ,
    last_activity_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Set on first successful /diagnosis. Makes submission idempotent (FR-7.6).
    diagnosis_submitted_at TIMESTAMPTZ,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT owner_is_exclusive CHECK (
        (user_id IS NOT NULL AND anonymous_id IS NULL) OR
        (user_id IS NULL AND anonymous_id IS NOT NULL)
    ),
    CONSTRAINT ended_when_terminal CHECK (
        (status = 'active') OR (ended_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX user_sequence_unique
    ON sessions (user_id, sequence_index) WHERE user_id IS NOT NULL;

CREATE INDEX ON sessions (user_id, started_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX ON sessions (anonymous_id) WHERE anonymous_id IS NOT NULL;
CREATE INDEX ON sessions (status, last_activity_at) WHERE status = 'active';
CREATE INDEX ON sessions (case_version_id);
```

**`ON DELETE RESTRICT` on `case_version_id` is deliberate.** A case version with sessions attached can never be deleted, because deleting it would orphan the only record of what a learner actually saw.

**`owner_is_exclusive`** encodes the trial model in the database rather than trusting the application.

**Session expiry.** A scheduled job marks sessions `expired` where `status = 'active' AND last_activity_at < now() - interval '7 days'` — implementing the 7-day resume window in `PRD` FR-4.

## 6.2 `session_events` — append-only

```sql
CREATE TYPE event_type AS ENUM (
    'question','patient_reply','examination','investigation',
    'early_diagnosis','diagnosis','feedback_viewed','input_blocked'
);

CREATE TABLE session_events (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    type        event_type NOT NULL,
    payload     JSONB NOT NULL,           -- shape per type in §8.2
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (session_id, seq)
);

CREATE INDEX ON session_events (session_id, seq);

CREATE TRIGGER session_events_append_only
  BEFORE UPDATE OR DELETE ON session_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

**`UNIQUE (session_id, seq)` is the concurrency control.** Two simultaneous requests computing the same next sequence number will collide, and one fails cleanly rather than silently interleaving. The application retries with a fresh sequence.

**`input_blocked`** records a real-patient-data block (`PRD` FR-4, `UX_SPEC` S-10) without storing the offending text — the payload holds only the detection reason. Storing it would defeat the purpose.

## 6.3 `session_results` — derived

```sql
CREATE TABLE session_results (
    session_id             UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,

    question_count         INTEGER NOT NULL,
    examination_count      INTEGER NOT NULL,
    investigation_count    INTEGER NOT NULL,
    duration_seconds       INTEGER,

    coverage_pct           NUMERIC(5,2) NOT NULL CHECK (coverage_pct BETWEEN 0 AND 100),
    topics_hit             TEXT[] NOT NULL,
    topics_missed          TEXT[] NOT NULL,

    diagnosis_submitted    TEXT NOT NULL,
    diagnosis_verdict      TEXT NOT NULL
                           CHECK (diagnosis_verdict IN ('correct','partial','anchored','other')),

    -- Scalars duplicated out of bias_detail for indexed analytical queries.
    anchoring_detected           BOOLEAN NOT NULL,
    anchoring_score              NUMERIC(4,3) NOT NULL CHECK (anchoring_score BETWEEN 0 AND 1),
    premature_closure_detected   BOOLEAN NOT NULL,
    premature_closure_score      NUMERIC(4,3) NOT NULL CHECK (premature_closure_score BETWEEN 0 AND 1),
    confirmation_bias_detected   BOOLEAN NOT NULL,
    confirmation_bias_score      NUMERIC(4,3) NOT NULL CHECK (confirmation_bias_score BETWEEN 0 AND 1),

    bias_detail             JSONB NOT NULL,   -- reason + evidence, §8.5
    exam_scorecard          JSONB NOT NULL,   -- §8.6
    investigation_scorecard JSONB NOT NULL,   -- §8.6

    key_investigations_done  SMALLINT NOT NULL,
    key_investigations_total SMALLINT NOT NULL,

    engine_version_id      UUID NOT NULL REFERENCES engine_versions(id),
    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON session_results (diagnosis_verdict);
CREATE INDEX ON session_results (anchoring_detected, premature_closure_detected, confirmation_bias_detected);
CREATE INDEX ON session_results USING gin (bias_detail);
CREATE INDEX ON session_results (engine_version_id);
```

**Why scalars are duplicated out of `bias_detail`:** every analytical query filters and aggregates on them (§11). JSONB extraction cannot use a btree index and is materially slower. The JSONB retains the reason and evidence strings needed for display (`PRD` P3).

**`key_investigations_done` and `_total` are stored, not derived**, because the *total* varies per case — this is exactly the denominator artefact that invalidated the pilot's key-test metric. Storing both makes the incomparability visible in the data rather than hidden in a ratio.

## 6.4 `engine_versions`

```sql
CREATE TABLE engine_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version           TEXT NOT NULL UNIQUE,      -- '1.3.0'
    detector_version  TEXT NOT NULL,
    lexicon_version   TEXT NOT NULL,
    encoder_model     TEXT,                      -- null while keyword-only

    -- The exact thresholds used. Shape in §8.7.
    thresholds        JSONB NOT NULL,

    is_current        BOOLEAN NOT NULL DEFAULT false,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX only_one_current_engine
    ON engine_versions (is_current) WHERE is_current;
```

**This table is what makes threshold calibration possible.** Every result records which engine produced it, so historical sessions can be replayed under candidate thresholds and the delta measured (`UX_SPEC` A-07, `TECH_SPEC` admin §4.8). It is also the mechanism that would have made the pilot's stale `0.88` confirmation scores a query rather than a forensic exercise.

## 6.5 `feedback_texts`

```sql
CREATE TABLE feedback_texts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

    lines         TEXT[] NOT NULL,
    generator     TEXT NOT NULL CHECK (generator IN ('llm','rule_fallback')),
    prompt_version TEXT,

    -- User feedback on the feedback (UX-3)
    was_helpful   BOOLEAN,
    rated_at      TIMESTAMPTZ,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON feedback_texts (session_id);
CREATE INDEX ON feedback_texts (generator, created_at DESC);
```

**Prompt bodies and model responses are not stored** — only the resulting lines. Storing prompts would duplicate the learner's own text into a second location for no analytical gain (`PLATFORM_SPEC` §3.7).

---

# 7. Operations

## 7.1 `llm_calls`

```sql
CREATE TABLE llm_calls (
    id            BIGSERIAL PRIMARY KEY,
    session_id    UUID REFERENCES sessions(id) ON DELETE SET NULL,

    purpose       TEXT NOT NULL
                  CHECK (purpose IN ('patient','feedback','extraction','judge','grounding')),
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,

    prompt_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      NUMERIC(10,6) NOT NULL,
    latency_ms    INTEGER NOT NULL,

    status        TEXT NOT NULL CHECK (status IN ('ok','retried','failed','fallback')),
    attempt       SMALLINT NOT NULL DEFAULT 1,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON llm_calls (created_at DESC);
CREATE INDEX ON llm_calls (purpose, model, created_at DESC);
CREATE INDEX ON llm_calls (session_id) WHERE session_id IS NOT NULL;
```

Drives the cost dashboard and the unit-economics metric in `PRD` §10.3. **`ON DELETE SET NULL`** rather than cascade: cost history must survive session deletion, since it is financial data.

## 7.2 `leakage_flags`

```sql
CREATE TABLE leakage_flags (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    event_seq      INTEGER NOT NULL,

    leaked_topics  TEXT[] NOT NULL,
    severity       TEXT NOT NULL CHECK (severity IN ('low','high')),

    reviewed       BOOLEAN NOT NULL DEFAULT false,
    confirmed      BOOLEAN,
    reviewed_by    UUID REFERENCES profiles(id),
    reviewed_at    TIMESTAMPTZ,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON leakage_flags (reviewed, severity, created_at DESC);
```

Implements the persona-leakage monitor. **`confirmed = true` excludes the session from research analysis** — the query in §11.7 applies this filter, because a session where the patient volunteered information is measuring the model, not the learner.

## 7.3 `idempotency_keys`

```sql
CREATE TABLE idempotency_keys (
    key          TEXT PRIMARY KEY,
    user_id      UUID REFERENCES profiles(id) ON DELETE CASCADE,
    endpoint     TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response     JSONB,
    status_code  SMALLINT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);

CREATE INDEX ON idempotency_keys (expires_at);
```

Serves `PRD` FR-7.6 (diagnosis submission) and FR-10.4 (Stripe webhooks). **`request_hash` guards against key reuse with a different body**, which should be a 422 rather than a silently replayed response.

## 7.4 `audit_log`

```sql
CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,
    actor_id     UUID REFERENCES profiles(id),
    action       TEXT NOT NULL,          -- 'case_version.published'
    entity_type  TEXT NOT NULL,
    entity_id    UUID,
    reason       TEXT,                   -- required for support access
    metadata     JSONB,
    ip_address   INET,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON audit_log (entity_type, entity_id, created_at DESC);
CREATE INDEX ON audit_log (actor_id, created_at DESC);

CREATE TRIGGER audit_log_append_only
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

Every admin action writes here (`PRD` FR-12.8). **`reason` is mandatory for support access to a user's session** (`PLATFORM_SPEC` §4.7) — enforced in the application, since a database check cannot know which actions require it.

## 7.5 `feature_flags`

```sql
CREATE TABLE feature_flags (
    key          TEXT PRIMARY KEY,
    is_enabled   BOOLEAN NOT NULL DEFAULT false,
    rollout_pct  SMALLINT NOT NULL DEFAULT 0 CHECK (rollout_pct BETWEEN 0 AND 100),
    description  TEXT,
    updated_by   UUID REFERENCES profiles(id),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Deliberately minimal (`PLATFORM_SPEC` §15.3 rejects a feature-flag SaaS). Bucketing is a stable hash of `(flag_key, user_id)` so a user's assignment does not flicker between requests.

---

# 8. JSONB schemas

JSONB is used where the shape evolves faster than migrations should. **Every JSONB column's shape is specified here and validated by a Pydantic model in the application** — "flexible" must not mean "undocumented."

## 8.1 `case_versions.content`

```jsonc
{
  "title": "The Chest Pain Trap",
  "patient": {
    "name": "Ramesh Kumar",
    "age": 48,
    "sex": "male",
    "presenting_complaint": "Chest pain for 3 days",
    "intro": "Ramesh is a 48-year-old accountant who…",
    "opening_line": "I've had this chest pain for about three days now…"
  },
  "system_prompt": "You are playing Ramesh Kumar… CRITICAL RULE: only reveal…",

  "correct_diagnosis": "GERD (NSAID-induced)",
  "accepted_diagnoses": ["gerd", "gastro-oesophageal reflux", "acid reflux"],
  "partial_diagnoses":  ["oesophagitis", "dyspepsia"],

  "anchor_topic": "cardiac / heart disease",
  "anchor_keywords":     ["heart", "cardiac", "angina", "ecg", "troponin"],
  "alternative_topics":  ["reflux", "antacid", "nsaid", "ibuprofen"],

  "required_topics": ["pain_character","meal_relationship","radiation",
                      "associated_symptoms","medications","family_history",
                      "duration_pattern","relieving_factors"],
  "minimum_questions": 7,

  "contradictory_clues": [
    ["burning", "heartburn"],
    ["after meal", "spicy", "coffee"],
    ["ibuprofen", "nsaid", "painkiller"]
  ],

  "examination": {
    "vitals":         { "key": true,  "finding": "HR 78, BP 132/84, afebrile." },
    "cardiovascular": { "key": true,  "finding": "Normal heart sounds…" },
    "abdomen":        { "key": true,  "finding": "Mild epigastric tenderness." },
    "respiratory":    { "key": false, "finding": "Clear to auscultation." }
  },

  "investigations": {
    "ecg":         { "category": "key",       "result": "Normal sinus rhythm…" },
    "troponin_0h": { "category": "key",       "result": "< 3 ng/L (normal)" },
    "ogd":         { "category": "key",       "result": "Erosive oesophagitis…" },
    "fbc":         { "category": "reasonable","result": "Hb 138 g/L…" },
    "ct_angiogram":{ "category": "low_value", "result": "No coronary stenosis." }
  }
}
```

**Invariants enforced in the application and by CI, not by the database:**

| # | Invariant | Rationale |
|---|---|---|
| C-1 | Every key in `examination` exists in `examinations.key` | Referential integrity across a JSON boundary |
| C-2 | Every key in `investigations` exists in `investigations.key` | Same |
| C-3 | Every entry in `required_topics` exists in `topic_lexicon.topic_key` | Same |
| C-4 | **`anchor_keywords` ∩ (any `contradictory_clues` entry) = ∅** | **The bug that cost 14 % sensitivity.** Blocks save in the admin editor |
| C-5 | `accepted_diagnoses` length ≥ 2 | Single-phrase matching is too brittle |
| C-6 | `contradictory_clues` length ≥ 4 | Below this, the 0.25 ratio is meaningless |
| C-7 | At least one `investigations` entry has `category: "key"` | Otherwise the scorecard denominator is zero |

C-4 is the one that matters most and is why the constraint is stated here rather than left to reviewer discipline.

## 8.2 `session_events.payload`

Shape varies by `type`. Discriminated union, validated on write.

```jsonc
// type = 'question'
{ "text": "Is the pain burning or crushing?", "char_count": 33 }

// type = 'patient_reply'
{ "text": "Burning, mostly.", "model": "llama-3.3-70b",
  "prompt_version": "case1-persona-v3", "latency_ms": 1840,
  "matched_topics": ["pain_character"] }

// type = 'examination'
{ "key": "vitals", "label": "Vital signs",
  "finding": "HR 78, BP 132/84, afebrile.", "was_case_specific": true }

// type = 'investigation'
{ "key": "ecg", "label": "ECG (12-lead)",
  "result": "Normal sinus rhythm…", "was_case_specific": true }

// type = 'diagnosis'
{ "text": "GERD" }

// type = 'input_blocked'
{ "reason": "suspected_patient_identifier" }   // never the offending text
```

**`matched_topics` on `patient_reply` rather than on `question`** — deliberate. It records what the *system understood*, evaluated at the time, under the engine version then current. Recomputation compares against this to detect drift.

## 8.3 `user_progress.bias_trends`

```jsonc
{
  "anchoring":         { "last10": 0.20, "prev10": 0.50, "direction": "improving" },
  "premature_closure": { "last10": 0.40, "prev10": 0.40, "direction": "stable" },
  "confirmation_bias": { "last10": 0.30, "prev10": 0.20, "direction": "declining" }
}
```

`direction` is precomputed so the UI never derives it — guaranteeing the wording in `UX_SPEC` S-16 is consistent. Values are flag *rates*, not scores.

## 8.4 `clinical_reviews.scores`

```jsonc
{
  "clinical_plausibility": 5,
  "internal_consistency":  4,
  "trap_validity":         5,
  "solvability":           4,
  "rubric_version": "v1"
}
```

Each 1–5. **Any dimension below 4 must not be recorded as `approved`** — enforced in the application. `rubric_version` allows the rubric to evolve without invalidating past reviews.

## 8.5 `session_results.bias_detail`

```jsonc
{
  "anchoring": {
    "detected": true,
    "score": 1.0,
    "rule_fired": "A1",
    "reason": "6 of your 6 questions focused on cardiac symptoms. You asked 1 question exploring alternative causes.",
    "evidence": ["Could this be a heart attack?", "Should we do an ECG?"],
    "counters": { "q": 6, "a": 6, "m": 1 }
  },
  "premature_closure": {
    "detected": true, "score": 0.62, "rule_fired": "P2",
    "reason": "You covered 3 of 8 key history areas before concluding.",
    "evidence": ["meal relationship", "radiation", "relieving factors"],
    "counters": { "q": 6, "q_min": 7, "coverage": 0.375 }
  },
  "confirmation_bias": {
    "detected": true, "score": 1.0, "rule_fired": "C1",
    "reason": "You explored 0 of 6 pieces of information that could have challenged your assumption.",
    "evidence": ["Only 0/6 contradictory areas explored"],
    "counters": { "k": 0, "K": 6 }
  }
}
```

**`counters` is the addition that makes replay verifiable.** Storing the intermediate values means a recomputation mismatch can be localised to a specific counter rather than merely observed as a different score.

**`rule_fired`** records which of the two OR-ed rules triggered — needed for the threshold-impact preview.

## 8.6 Scorecard JSONB

```jsonc
{
  "key_done":       ["Vital Signs", "Cardiovascular Examination"],
  "key_missed":     ["Abdominal Examination"],
  "relevant_done":  ["General Inspection"],
  "low_value_done": [],
  "extra_done":     []
}
```

Labels, not keys — these render directly. The keys live in `session_events` if a machine-readable form is needed.

## 8.7 `engine_versions.thresholds`

```jsonc
{
  "anchoring":         { "concentration": 0.60, "min_questions": 4,
                         "a2_min_anchor": 3, "a2_score": 0.85 },
  "premature_closure": { "coverage": 0.60, "score_floor": 0.10 },
  "confirmation_bias": { "clue_ratio": 0.25, "min_questions": 5, "c1_score": 0.90 },
  "topic_matching":    { "mode": "keyword", "similarity_threshold": null }
}
```

**Every constant that affects a result is here**, not in code (`ADR-0004`, `TECH_SPEC` §4.4). This is what makes replay under candidate thresholds a data operation.

---

# 9. Migrations and seed

## 9.1 Migration sequence

Alembic, hand-written, reviewed (`PLATFORM_SPEC` §3.5). Order is dependency-driven.

| # | Migration | Creates |
|---|---|---|
| 001 | `extensions` | pgcrypto, citext, vector, pg_trgm |
| 002 | `functions` | `set_updated_at`, `forbid_mutation` |
| 003 | `enums` | all 6 enum types |
| 004 | `profiles` | `profiles` + indexes + trigger |
| 005 | `content_master` | `examinations`, `investigations`, `topic_lexicon`, `topic_phrases` |
| 006 | `cases` | `cases`, `case_versions`, `clinical_reviews` |
| 007 | `case_publish_gate` | `require_clinical_approval` trigger |
| 008 | `engine_versions` | `engine_versions` |
| 009 | `sessions` | `sessions` + constraints + indexes |
| 010 | `session_events` | `session_events` + append-only trigger |
| 011 | `session_results` | `session_results` |
| 012 | `feedback` | `feedback_texts` |
| 013 | `commerce` | `subscriptions` |
| 014 | `progress` | `user_progress`, `user_case_history` |
| 015 | `ops` | `llm_calls`, `leakage_flags`, `idempotency_keys`, `audit_log`, `feature_flags` |
| 016 | `rls` | Row-Level Security policies (§10) |
| 017 | `seed_content` | 27 examinations, 86 investigations, 40 topics, 523 phrases |
| 018 | `seed_engine` | Engine version `1.0.0` with current thresholds |

**Migration 007 must follow 006**, since the trigger references `clinical_reviews`.

## 9.2 Seed data

| Table | Rows | Source |
|---|---|---|
| `examinations` | 27 | `MASTER_EXAMINATIONS` in the existing `cases.py` |
| `investigations` | 86 | `MASTER_INVESTIGATIONS` |
| `topic_lexicon` | 40 | `TOPIC_KEYWORDS` keys |
| `topic_phrases` | 523 | `TOPIC_KEYWORDS` values |
| `engine_versions` | 1 | Current thresholds, `is_current = true` |
| `cases` / `case_versions` | 5 | Existing cases, migrated as v1, status `draft` |

**The 5 migrated cases enter as `draft`, not `published`.** They must pass clinical review before going live (FR-12.5) — including the ones that already ran in the pilot. Publishing them without review would make the trigger a formality.

**Development seed additionally creates:** 3 test users (free, pro, admin), 1 approving clinical review per case so cases can be published locally, and ~10 synthetic sessions for dashboard development.

## 9.3 Migrating the 16 pilot sessions

Optional, run once. The pilot JSON files (`sessions/*.json`) become:

1. A `profiles` row per participant — email `NULL`, `research_pid` set from the original `participant_id` (`P01`…`P08`)
2. `sessions` rows with `sequence_index` from `session_sequence`, `status = 'completed'`
3. **Synthesised `session_events`** — the JSON preserves questions, exams and investigations as separate blocks but not their interleaving, so events are emitted block-ordered with `"provenance": "backfilled"` in the payload
4. `session_results` inserted verbatim, `engine_version` = a dedicated `pilot-2026-07` row

> ⚠️ **Backfilled events carry a provenance marker and must be excluded from any timing analysis.** Their timestamps are synthetic. Any query computing think-time must filter them out.

## 9.4 Zero-downtime rules

Expand → migrate → contract. Never drop a column in the same release that stops writing it.

| Change | Safe approach |
|---|---|
| Add a column | Nullable or with a default; backfill separately |
| Rename | Add new, dual-write, backfill, switch reads, drop old — four releases |
| Add `NOT NULL` | Add nullable → backfill → add constraint `NOT VALID` → `VALIDATE` |
| Add an index | `CREATE INDEX CONCURRENTLY`, outside a transaction |
| Add an enum value | `ALTER TYPE … ADD VALUE`, own migration, no other DDL |

---

# 10. Security and privacy

## 10.1 Row-Level Security

Defence in depth (`PLATFORM_SPEC` §7.3). An application bug then fails closed.

```sql
ALTER TABLE profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_events   ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_results  ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_texts   ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_progress    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_case_history ENABLE ROW LEVEL SECURITY;

-- Users see only themselves
CREATE POLICY own_profile ON profiles
  FOR ALL USING (id = auth.uid());

CREATE POLICY own_sessions ON sessions
  FOR ALL USING (user_id = auth.uid());

-- Child tables inherit via their parent session
CREATE POLICY own_session_events ON session_events
  FOR ALL USING (EXISTS (
    SELECT 1 FROM sessions s
    WHERE s.id = session_events.session_id AND s.user_id = auth.uid()));

CREATE POLICY own_session_results ON session_results
  FOR ALL USING (EXISTS (
    SELECT 1 FROM sessions s
    WHERE s.id = session_results.session_id AND s.user_id = auth.uid()));

-- Feedback inherits through its session, like session_results
CREATE POLICY own_feedback_texts ON feedback_texts
  FOR ALL USING (EXISTS (
    SELECT 1 FROM sessions s
    WHERE s.id = feedback_texts.session_id AND s.user_id = auth.uid()));

-- Directly user-owned
CREATE POLICY own_subscriptions ON subscriptions
  FOR ALL USING (user_id = auth.uid());

CREATE POLICY own_progress ON user_progress
  FOR ALL USING (user_id = auth.uid());

CREATE POLICY own_case_history ON user_case_history
  FOR ALL USING (user_id = auth.uid());

-- Published content is world-readable; only admins write
CREATE POLICY read_published_cases ON case_versions
  FOR SELECT USING (status = 'published');
```

**Enabling RLS without writing a policy denies everything.** The last four
policies above were missing from this section until T-013, which meant
`feedback_texts`, `subscriptions`, `user_progress` and `user_case_history` were
not loosely protected but entirely unreachable by the application — every query
returning nothing, with no error to explain it. Added by migration 021, and
guarded as a property of the schema by
`test_every_rls_enabled_table_has_at_least_one_policy` so a table added later
cannot repeat it quietly.

**Anonymous trial sessions bypass RLS by necessity** — there is no `auth.uid()`. They are served through a service-role connection with an explicit `anonymous_id` filter in the query, and that code path is short, isolated, and separately tested.

## 10.2 Deletion and erasure

When a user deletes their account:

```sql
BEGIN;
  UPDATE subscriptions SET status = 'cancelled'
   WHERE user_id = :uid AND status IN ('active','trialing','past_due');

  UPDATE profiles SET
      display_name      = NULL,
      professional_role = NULL,
      year_of_training  = NULL,
      country           = NULL,
      institution_id    = NULL,
      consent_research  = false,
      deleted_at        = now()
   WHERE id = :uid;
  -- research_pid is deliberately retained.

  -- Free-text the user wrote is redacted; structure is kept.
  UPDATE session_events
     SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
   WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)
     AND type IN ('question','diagnosis');
COMMIT;
-- auth.users deletion is issued separately via the Supabase admin API.
```

**What is retained and why:** `session_results` and the `research_pid` link survive, because published analyses must remain reproducible. **This must be stated plainly in the participant information and the deletion confirmation screen** (`UX_SPEC` S-20) — a user has a right to know what does not disappear.

## 10.3 Retention

| Data | Retention | Then |
|---|---|---|
| `session_events` free text | 24 months | Redacted, structure kept |
| `session_results` | Indefinite | Anonymous once detached |
| `llm_calls` | 24 months | Aggregated to daily totals, rows dropped |
| `audit_log` | 24 months | Archived to cold storage |
| `idempotency_keys` | 24 hours | Deleted by scheduled job |
| LLM prompt/response bodies | **Never stored** | — |

---

# 11. Query patterns

The queries that matter, written before the schema was fixed — which is how the indexes above were chosen.

## 11.1 Case selection (`PRD` FR-3.1)

```sql
SELECT cv.id, cv.case_id, cv.title, cv.content->'patient' AS patient
FROM case_versions cv
WHERE cv.status = 'published'
  AND cv.case_id NOT IN (
      SELECT case_id FROM user_case_history WHERE user_id = :uid)
ORDER BY random()
LIMIT 1;
```
*Uses the partial index on `status`. If empty, falls back to least-recently-attempted.*

## 11.2 Free-tier allowance (`PRD` FR-10.1)

```sql
SELECT count(*) AS used_this_month
FROM sessions
WHERE user_id = :uid
  AND started_at >= date_trunc('month', now() AT TIME ZONE :tz);
```
*Counts every started session regardless of status — abandonment counts against the limit (FR-3, edge cases).*

## 11.3 Session reconstruction (`ADR-0003`)

```sql
SELECT seq, type, payload, created_at
FROM session_events
WHERE session_id = :sid
ORDER BY seq;
```
*Covered by `(session_id, seq)`. ~20 rows; sub-millisecond.*

## 11.4 Subscription drift reconciliation

```sql
SELECT p.id, p.subscription_tier AS profile_says, s.tier AS subscription_says
FROM profiles p
LEFT JOIN subscriptions s
       ON s.user_id = p.id AND s.status IN ('active','trialing')
WHERE p.deleted_at IS NULL
  AND p.subscription_tier IS DISTINCT FROM COALESCE(s.tier, 'free');
```
*Runs nightly. Any row is a bug in the webhook handler. Should always return zero.*

## 11.5 Rebuild `user_progress`

```sql
WITH completed AS (
  SELECT s.user_id, s.id, r.coverage_pct,
         r.anchoring_detected, r.premature_closure_detected,
         r.confirmation_bias_detected,
         row_number() OVER (PARTITION BY s.user_id ORDER BY s.ended_at DESC) AS rn
  FROM sessions s
  JOIN session_results r ON r.session_id = s.id
  WHERE s.status = 'completed' AND s.user_id IS NOT NULL
)
SELECT user_id,
       count(*)                                          AS sessions_completed,
       avg(coverage_pct) FILTER (WHERE rn <= 10)         AS mean_coverage_last10,
       avg(anchoring_detected::int) FILTER (WHERE rn <= 10)  AS anchoring_last10,
       avg(anchoring_detected::int) FILTER (WHERE rn BETWEEN 11 AND 20) AS anchoring_prev10
FROM completed
GROUP BY user_id;
```

## 11.6 Case difficulty (anti-answer-sharing, `ADR-0014`)

```sql
SELECT cv.case_id, cv.title,
       count(*)                                              AS attempts,
       avg((r.diagnosis_verdict = 'anchored')::int)::numeric(4,3) AS trap_rate,
       avg(r.coverage_pct)::numeric(5,2)                     AS mean_coverage
FROM session_results r
JOIN sessions s      ON s.id = r.session_id
JOIN case_versions cv ON cv.id = s.case_version_id
WHERE s.ended_at > now() - interval '90 days'
GROUP BY cv.case_id, cv.title
HAVING count(*) >= 20
ORDER BY trap_rate ASC;
```
*A collapsing `trap_rate` is evidence of answer circulation. Surfaced in the admin case bank.*

## 11.7 Research export (de-identified)

```sql
SELECT p.research_pid, s.sequence_index, cv.case_id,
       r.coverage_pct, r.question_count, r.diagnosis_verdict,
       r.anchoring_detected, r.premature_closure_detected,
       r.confirmation_bias_detected,
       r.key_investigations_done, r.key_investigations_total,
       ev.version AS engine_version
FROM session_results r
JOIN sessions s        ON s.id  = r.session_id
JOIN profiles p        ON p.id  = s.user_id
JOIN case_versions cv  ON cv.id = s.case_version_id
JOIN engine_versions ev ON ev.id = r.engine_version_id
WHERE p.consent_research = true
  AND s.status = 'completed'
  AND NOT EXISTS (
      SELECT 1 FROM leakage_flags lf
      WHERE lf.session_id = s.id AND lf.confirmed = true)
ORDER BY p.research_pid, s.sequence_index;
```

**Three protections in one query:** consent is required, leakage-confirmed sessions are excluded, and `research_pid` is selected rather than any identifier. **No email column appears** — that is deliberate and should be preserved in any variation.

## 11.8 LLM cost per completed session

```sql
SELECT date_trunc('day', s.ended_at)::date AS day,
       count(DISTINCT s.id)                AS sessions,
       sum(c.cost_usd)                     AS total_cost,
       (sum(c.cost_usd) / count(DISTINCT s.id))::numeric(10,4) AS cost_per_session
FROM sessions s
JOIN llm_calls c ON c.session_id = s.id
WHERE s.status = 'completed' AND s.ended_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 1 DESC;
```
*Drives NFR-7 (< $0.05/session). The unit economic that decides whether the business works.*

---

# 12. Forward declarations

Designed now, **not created in v1**. Recorded so adding them requires no restructuring.

| Table | For | Trigger to build |
|---|---|---|
| `institutions` | B2B cohorts (`ADR-0015`) | An institution commits |
| `cohorts`, `cohort_members` | Educator assignment | With `institutions` |
| `studies`, `study_enrolments` | Controlled research (`PLATFORM_SPEC` §10.3) | Ethics approval obtained |
| `case_ingestion_runs` | Case Factory provenance | Phase 7 |
| `case_variants` | Anti-answer-sharing (`ADR-0014`) | When the bank exceeds ~30 cases |
| `notification_preferences` | Push/email | Mobile app |

**Already accommodated in v1:** `profiles.institution_id` is nullable, `case_versions` carries `source_dataset` / `source_record_id` / `qa_report`, and `sessions` can gain a `study_arm` column without touching existing rows.

---

# 13. Open questions

| # | Question | Recommendation |
|---|---|---|
| DM-1 | Partition `session_events` by month? | **No.** Postgres handles tens of millions unpartitioned. Revisit past ~50 M rows |
| DM-2 | Store `content` as JSONB or normalise into tables? | **JSONB.** The shape is authored as a unit, versioned as a unit, and read as a unit. Normalising would mean ~8 joins per case load |
| DM-3 | Should `research_pid` survive account deletion? | **Yes** — reproducibility of published analyses. Must be disclosed (§10.2) |
| DM-4 | Read replica for analytics? | Not yet. Add when analytical queries measurably affect write latency |
| DM-5 | Encrypt `session_events.payload` at rest? | Supabase encrypts at rest already. Column-level encryption would break the recomputation check (`ADR-0005`) — **do not** |

---

*End of Data Model. `API_CONTRACT.md` is next.*
