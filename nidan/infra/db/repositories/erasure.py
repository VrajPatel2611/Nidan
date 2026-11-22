"""
Account erasure — `DATA_MODEL` §10.2, unblocked by migration 033 (API-9).

One transaction, four statements, and the reason each one is here.

**It runs as the user, in the user's own scope.** The route's first instinct
was a `ServiceActor`, and that was wrong twice over: `AuditRepository.record`
takes the actor from the scope and refuses to be told who acted, so a service
actor has no id to attribute the erasure to; and a second scope for the audit
row would let the proof and the act commit separately. Running as the learner
makes it atomic and makes `actor_id` true — they did ask.

Every statement is still scoped by an explicit `user_id` as well as by RLS.
The redundancy is deliberate: `ADR-0016` wants the policy as the last line of
defence, not the first, and these four statements are the ones where getting
the scope wrong would redact somebody else's consultation.

## What is removed

| Where | What | Why |
|---|---|---|
| `subscriptions` | status → `cancelled` | §10.2; billing must stop before the identity goes |
| `profiles` | name, role, year, country, institution, consent | §10.2; `deleted_at` stamped |
| `session_events` | every `payload->'text'` → `"[redacted]"` | the learner's own prose, and the patient replies generated from it |
| `feedback_texts` | `lines` → `{[redacted]}` | prose that **cites the learner's questions** (`PRD` P3) |

## What is kept, and why it is not an oversight

`session_results`, `research_pid`, and the structure of every event —
`char_count`, the examination keys, the `input_blocked` reasons. §10.2 retains
them so published analyses stay interpretable, `UX_SPEC` S-20 says so on the
screen before the user clicks, and `DATA_MODEL` §11.7's research export reads
`session_results` **only** — it selects no text column at all, which is why
redacting the prose costs the research nothing.

`audit_log` is kept and keeps its unconditional append-only trigger. It is the
record that the erasure happened, which is the one thing you must be able to
prove afterwards.

## Three things this deliberately does not do

- **It does not delete rows.** Migration 033 permits redaction and nothing
  else; a gap in a session's `seq` is indistinguishable from a bug.
- **It does not name the event types it redacts.** The predicate is
  `payload ? 'text'`, so an event type added later is covered the day it is
  added rather than the day someone remembers this file.
  `test_every_text_bearing_event_type_is_covered` pins the set so adding one
  is still a conscious act.
- **It does not touch `auth.users`.** Supabase owns credentials (`ADR-0002`),
  so that is an admin-API call the worker makes — and until it does, the
  user's token stays valid, which is why `ProfileRepository.get()` now hides a
  soft-deleted profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

# Mirrors `REDACTED` in `migrations/versions/033_erasure.py`. The trigger
# compares the new payload against this exact literal, so a disagreement makes
# every erasure raise "append-only" — the original API-9 symptom, returning
# under a different cause. `test_the_redaction_literal_matches_the_migration`
# is what stops that.
REDACTED = "[redacted]"


@dataclass(frozen=True)
class Erasure:
    """
    What the transaction changed. Written to `audit_log` as the proof.

    Counts, never content — the same rule as `domain/guard.py`. An audit row
    saying which text was redacted would be the erasure storing what it
    erased.
    """

    events_redacted: int
    feedback_redacted: int
    subscriptions_cancelled: int


class ErasureRepository(Repository):

    def erase(self, user_id: UUID) -> Erasure:
        """
        Execute `DATA_MODEL` §10.2 for one user.

        `user_id` is an argument as well as implied by the actor, so the
        `WHERE` clauses below are written out in full where
        `ProfileRepository`'s are not. RLS would scope all four statements on
        its own; these are the statements where a scoping mistake redacts
        somebody else's consultation irreversibly, so they say so themselves
        and the policy is what catches the mistake rather than what prevents
        it.

        Idempotent. Re-running it redacts already-redacted rows to the same
        value, which migration 033's predicate permits, and re-stamps nothing:
        `deleted_at` is set with COALESCE so the first erasure keeps its date.
        """
        # Billing first. If a later statement fails the whole transaction
        # rolls back, but of the four this is the one whose failure would keep
        # charging a person who has asked to be forgotten.
        cancelled = self._conn.execute(sa.text("""
            UPDATE subscriptions SET status = 'cancelled'
             WHERE user_id = :uid
               AND status IN ('active', 'trialing', 'past_due')
        """), {"uid": user_id}).rowcount

        # §10.2's field list. `research_pid` is deliberately NOT nulled — it is
        # what keeps an already-published analysis interpretable, and S-20
        # tells the user it survives before they confirm.
        #
        # `consent_research = false` stops all future processing, which is what
        # withdrawing consent means; §11.7 filters on it, so these sessions
        # leave the next export.
        self._conn.execute(sa.text("""
            UPDATE profiles SET
                display_name      = NULL,
                professional_role = NULL,
                year_of_training  = NULL,
                country           = NULL,
                institution_id    = NULL,
                consent_research  = false,
                deleted_at        = COALESCE(deleted_at, now())
             WHERE id = :uid
        """), {"uid": user_id})

        # Every event carrying free text, in one statement. Migration 033
        # permits exactly this shape and refuses any other, so a mistake here
        # fails loudly instead of mutating the log.
        events = self._conn.execute(sa.text(f"""
            UPDATE session_events
               SET payload = jsonb_set(payload, '{{text}}', '"{REDACTED}"')
             WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)
               AND payload ? 'text'
        """), {"uid": user_id}).rowcount

        # The gap §10.2 did not mention. Feedback prose cites the learner's own
        # questions by design (`PRD` P3, `ADR-0004`) — without this their words
        # survive verbatim in a table the erasure never looked at.
        #
        # `lines` is `TEXT[] NOT NULL`, so it becomes a one-element tombstone
        # rather than an empty array: an auditor reading the row should see
        # that text was removed, not an absence they have to interpret.
        feedback = self._conn.execute(sa.text("""
            UPDATE feedback_texts
               SET lines = ARRAY[:redacted]::text[]
             WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)
               AND lines <> ARRAY[:redacted]::text[]
        """), {"uid": user_id, "redacted": REDACTED}).rowcount

        return Erasure(events_redacted=events,
                       feedback_redacted=feedback,
                       subscriptions_cancelled=cancelled)
