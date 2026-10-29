# Onboarding a clinical reviewer

Everything needed to take a clinician from "has agreed to help" to "has
reviewed a case". Written for whoever is running the project, not for the
reviewer — what *they* receive is `REVIEWER_GUIDE.md`.

T-023 finished on 29 October 2026, which is what makes this possible: before
it, only a programmer could read a case.

---

## What a reviewer can and cannot do

Worth being precise about, because the answer surprises people in both
directions.

| | |
|---|---|
| **Can** | See the review queue · open any draft in Playtest and talk to the patient · score the rubric · approve, request changes, or reject |
| **Cannot** | Edit a case. Publish one. See learners, sessions, results, or anything commercial |

The restriction is in the database, not the interface. `nidan_reviewer` has no
write grant on `cases` or `case_versions` (migration 023), so a reviewer who
found an unguarded form still could not change content. That is deliberate:
**a reviewer who edits a case is no longer reviewing it.**

Since migration 025 a reviewer can also see other privileged profiles — only
those — which is what puts a name next to "reviewed by" rather than "a
reviewer".

---

## 1 · Create the account

In the Supabase dashboard: **Authentication → Users → Add user → Create new
user.**

**Tick "Auto Confirm User."** Without it their first sign-in fails with
`email_not_confirmed`, which looks like a wrong password.

Use their real work email. Copy the **User UID**.

> Do not reuse one account between two reviewers. `clinical_reviews.reviewer_id`
> is the only record of who judged a case, and two people behind one id makes
> the review data worthless for the exact question it exists to answer.

## 2 · Grant the role

```bash
python scripts/provision_reviewer.py \
  --uid <user-uid> --name "Dr Asha Nair" \
  --timezone Asia/Kolkata --by <your-admin-uid>
```

Add `--dry-run` first if you want to see what it would do.

The script refuses rather than guesses. It will stop if the account does not
exist in Supabase, if the uid already belongs to someone with a different role,
or if the profile was soft-deleted — each with a sentence saying which. It
writes an `audit_log` row for every change; granting the right to approve
clinical content is the most consequential thing an admin does.

`--by` is optional and worth giving: without it the audit row records what was
done but not by whom.

**It never writes to `auth.users` on Supabase**, and refuses `--create-auth-user`
unless it can prove it is looking at the three-column local stub from migration
001. Forging a row there would produce an account with full reviewer privilege,
no password, and no entry in the dashboard's user list.

Confirm:

```bash
psql "$DATABASE_URL" -c "SELECT display_name, platform_role FROM profiles WHERE platform_role <> 'user';"
```

## 3 · Assign them something to review

From `/admin/reviews`, **All pending** → pick a version → assign. An unassigned
draft is visible but reads as nobody's job; an assigned one appears under their
**Assigned to me** on sign-in.

Start each reviewer with **one** case. The first review is where they discover
what the rubric means, and it is cheaper to correct that understanding once
than across five cases.

Give the two reviewers **the same first case**, independently. Comparing two
first reviews of one case tells you whether the rubric is being read the same
way — and that is worth more at this stage than two more cases reviewed.

## 4 · Send them three things

1. **`REVIEWER_GUIDE.md`** — or the generated `Nidan_Reviewer_Guide.docx`, which
   is what most clinicians would rather open
2. **The URL** of the console
3. **Their password**, by a different channel from the URL

Never the `service_role` key, and never anything from `.env`.

## 5 · Check it worked, before they try

Signing in as them is the only way to be sure, and the console gives no
diagnostic if it is wrong: `UX_SPEC` §12.1 requires every refusal — no token,
expired token, signed in without privilege — to return an identical 404.

`LOCAL_ADMIN_ACCESS.md` §4 shows how to get a token; the same steps work for a
reviewer. Then:

```bash
curl -s -o /dev/null -w 'reviews -> %{http_code}\n' \
  -H "Authorization: Bearer $TOK" http://localhost:8000/admin/reviews
```

200 means the whole chain works: token verified against the project's JWKS,
`aud` and `iss` matched, profile found, role sufficient.

---

## Where they will actually be reviewing

**The console has to be somewhere they can reach it.** It runs on
`localhost:8000` and there is no deployment task anywhere in `BUILD_PLAN` —
T-045 is "launch readiness", not hosting. Two clinicians cannot review cases on
a laptop in Ahmedabad.

Nothing about a *case* is deployed; cases are rows, and migration 019 already
seeded the five as drafts. What needs a public URL is the Flask app that is
already built, pointed at the Supabase Postgres from `ADR-0017`. The learner-
facing web app is T-032 and has nothing to do with this.

So this is two steps, in order:

1. `SUPABASE_DEPLOYMENT.md` — the 25 migrations against the Supabase project
2. The container somewhere with a URL, `DATABASE_URL` pointing at Supabase

---

## When it 404s

The refusal is identical in every case, so work down the list rather than
guessing. `LOCAL_ADMIN_ACCESS.md` has the full table; the two that bite a
*reviewer* specifically:

| Cause | How to tell |
|---|---|
| Profile has `platform_role = 'user'` | `SELECT platform_role FROM profiles WHERE id = '<uid>';` — the script would have said so; a hand-written `INSERT` would not |
| Reviewer reached an admin-only route | `/admin/reviews` is theirs. The case editor and publish are not, and refuse the same way |

`docker compose logs app --tail 50` distinguishes them. The response is silent
outward and the log is legible inward; that asymmetry is the design.

---

## When someone stops reviewing

Set the role back:

```bash
python scripts/provision_reviewer.py --uid <uid> --name "Dr Asha Nair" --role user --force
```

`--force` is required, and that is the point: a demotion should be as
deliberate as the grant. Their past reviews stay — `clinical_reviews` is
evidence, and a published case's approval must remain attributable.

---

## Related

- `REVIEWER_GUIDE.md` — what the reviewer receives
- `LOCAL_ADMIN_ACCESS.md` — tokens, cookies, and why every failure looks the same
- `SUPABASE_DEPLOYMENT.md` — the schema on Supabase
- `UX_SPEC` §12.6 — the queue and the rubric
- `DATA_MODEL` §5.2, §8.4 — `clinical_reviews` and the scores JSONB
